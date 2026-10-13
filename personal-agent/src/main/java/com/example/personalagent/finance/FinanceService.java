package com.example.personalagent.finance;

import com.example.personalagent.storage.Store;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

import java.math.BigDecimal;
import java.math.MathContext;
import java.math.RoundingMode;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicReference;
import java.util.function.Supplier;

import static com.example.personalagent.Api.*;

/** Exact, local personal ledger; observations are checkpoints, never transactions. */
@Service
public class FinanceService {
    private static final BigDecimal ZERO = BigDecimal.ZERO;
    private static final MathContext PRECISION = new MathContext(60, RoundingMode.HALF_EVEN);
    private static final String EPOCH = "0001-01-01T00:00:00Z";
    private static final Set<String> TYPES = new HashSet<>(Arrays.asList("income", "expense", "transfer", "buy", "sell",
            "dividend", "interest", "borrow", "repay", "asset_purchase", "valuation_adjustment",
            "balance_observation", "position_observation", "liability_observation"));
    private static final Set<String> NUMBERS = new HashSet<>(Arrays.asList("amount", "quantity", "price", "fee", "interest", "loan_amount", "target_amount"));
    private static final Set<String> FIELDS = new HashSet<>(Arrays.asList("type", "occurred_at", "account_id", "to_account_id", "asset_id", "liability_id",
            "amount", "quantity", "price", "fee", "interest", "loan_amount", "target_amount", "note", "source", "external_id", "idempotency_key", "supersedes_id", "expected_revision"));
    private final Store store;
    private final Supplier<Instant> clock;
    private QuoteProvider quotes;
    private final ObjectMapper json = new ObjectMapper();
    private long cachedRevision = -1;
    private Map<String, Map<String, Object>> cachedState;
    private String cachedAsOf;
    private final Map<String, Map<String, Object>> cashflowCache = new HashMap<>();

    @Autowired public FinanceService(Store store) { this(store, Instant::now, new QuoteProvider()); }
    public FinanceService(Store store, Supplier<Instant> clock, QuoteProvider quotes) {
        this.store = store; this.clock = clock; this.quotes = quotes;
    }
    public void setQuoteProvider(QuoteProvider provider) { this.quotes = provider; }
    public synchronized void invalidateCache() { cachedRevision = -1; cashflowCache.clear(); }
    private String now() { return clock.get().toString(); }

    private static Map<String, Map<String, Object>> collection(Map<String, Map<String, Map<String, Object>>> all, String name) {
        return all.computeIfAbsent("finance_" + name, key -> new LinkedHashMap<>());
    }
    private static long revision(Map<String, Map<String, Map<String, Object>>> all, String key) {
        Map<String, Object> meta = collection(all, "meta").get("ledger");
        return meta == null || meta.get(key) == null ? 0 : ((Number) meta.get(key)).longValue();
    }
    private long revision(String key) {
        Map<String, Object> meta = store.get("finance_meta", "ledger");
        return meta == null || meta.get(key) == null ? 0 : ((Number) meta.get(key)).longValue();
    }
    private static long bump(Map<String, Map<String, Map<String, Object>>> all, String key) {
        Map<String, Object> meta = collection(all, "meta").computeIfAbsent("ledger", id -> map("revision", 0, "quote_revision", 0, "sequence", 0));
        long next = ((Number) meta.get(key)).longValue() + 1;
        meta.put(key, next); return next;
    }
    private static void expected(Map<String, Map<String, Map<String, Object>>> all, Map<String, Object> input) {
        Object expected = input.get("expected_revision");
        if (expected != null) {
            if (!(expected instanceof Number)) throw conflict("账本已变化，请刷新后再提交");
            try { if (new BigDecimal(expected.toString()).longValueExact() != revision(all, "revision")) throw conflict("账本已变化，请刷新后再提交"); }
            catch (ArithmeticException invalid) { throw conflict("账本版本必须是整数，请刷新后再提交"); }
        }
    }
    private static String string(Object value, String label, int max, boolean required) {
        require(value == null || value instanceof String, label + "必须是文本");
        String result = value == null ? "" : ((String) value).trim();
        require(result.length() <= max && (!required || !result.isEmpty()), label + "长度无效");
        return result;
    }
    private static String currency(Object value) {
        String result = string(value == null ? "CNY" : value, "币种", 3, true).toUpperCase(Locale.ROOT);
        require(result.matches("[A-Z]{3}"), "币种必须是三个大写字母"); return result;
    }
    private static int scale(String currency) { return "JPY".equals(currency) ? 0 : "KWD".equals(currency) || "BHD".equals(currency) ? 3 : 2; }
    private static BigDecimal decimal(Object value, String label, String fallback, boolean positive, int scale) {
        if (value == null || "".equals(value)) value = fallback;
        require(value instanceof String && ((String) value).matches("\\d{1,28}(?:\\.\\d{1,12})?"), label + "必须是十进制字符串，不支持浮点数或科学计数法");
        BigDecimal result = new BigDecimal((String) value);
        require(result.scale() <= scale && (positive ? result.signum() > 0 : result.signum() >= 0), label + "范围或精度无效"); return result;
    }
    private static BigDecimal number(Object value, String label, String fallback, boolean positive) { return decimal(value, label, fallback, positive, 12); }
    private static BigDecimal money(Object value, String label, String currency, String fallback, boolean positive) { return decimal(value, label, fallback, positive, scale(currency)); }
    private static String num(BigDecimal value) { return value.signum() == 0 ? "0" : value.stripTrailingZeros().toPlainString(); }
    private static BigDecimal bd(Object value) { return new BigDecimal(String.valueOf(value)); }
    private static String timestamp(Object value) {
        String input = string(value, "时间", 60, true);
        try { return Instant.parse(input).toString(); } catch (RuntimeException ignored) { }
        try { return OffsetDateTime.parse(input).toInstant().toString(); } catch (RuntimeException ignored) { }
        try { return LocalDateTime.parse(input).toInstant(ZoneOffset.ofHours(8)).toString(); } catch (RuntimeException ignored) { }
        try { return LocalDate.parse(input).atStartOfDay().toInstant(ZoneOffset.ofHours(8)).toString(); }
        catch (RuntimeException ignored) { throw new ResponseStatusException(HttpStatus.UNPROCESSABLE_ENTITY, "时间格式无效，请使用日期或 ISO 时间"); }
    }
    private static int compareTime(String a, String b) { return Instant.parse(a).compareTo(Instant.parse(b)); }
    private void past(String asOf) { require(compareTime(asOf, now()) <= 0, "发生/截至时间不能在未来"); }
    private String hash(Object value) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] bytes = digest.digest(json.writeValueAsBytes(value));
            StringBuilder result = new StringBuilder(); for (byte b : bytes) result.append(String.format("%02x", b)); return result.toString();
        } catch (Exception ignored) { throw new IllegalStateException("无法生成本地记录标识"); }
    }
    private String requestKey(Map<String,Object> input,String kind) {
        return input.get("idempotency_key")==null ? null : kind+":"+string(input.get("idempotency_key"),"幂等键",100,true);
    }
    private String requestSignature(Map<String,Object> input) {
        Map<String,Object> body=new TreeMap<>(input);body.remove("expected_revision");body.remove("idempotency_key");return hash(body);
    }
    private Map<String,Object> replayEntity(Map<String,Map<String,Map<String,Object>>> all,Map<String,Object> input,String kind,String requestKey) {
        if(requestKey==null)return null;Map<String,Object> previous=collection(all,"requests").get(requestKey);if(previous==null)return null;
        if(!requestSignature(input).equals(previous.get("signature")))throw conflict("相同幂等键对应不同内容，请刷新并核对");
        return collection(all,kind).get(text(previous,"entity_id"));
    }
    private void rememberEntity(Map<String,Map<String,Map<String,Object>>> all,Map<String,Object> input,String requestKey,String entityId) {
        if(requestKey!=null)collection(all,"requests").put(requestKey,map("entity_id",entityId,"signature",requestSignature(input)));
    }
    private static Map<String, Object> account(Map<String, Map<String, Map<String, Object>>> all, Object accountId) {
        String id = string(accountId, "账户 ID", 100, true);
        Map<String, Object> result = collection(all, "accounts").get(id);
        if (result == null) throw new ResponseStatusException(HttpStatus.NOT_FOUND, "账户不存在"); return result;
    }
    private static Map<String, Object> asset(Map<String, Map<String, Map<String, Object>>> all, Object assetId, String kind) {
        String id = string(assetId, "资产 ID", 100, true);
        Map<String, Object> result = collection(all, "assets").get(id);
        if (result == null) throw new ResponseStatusException(HttpStatus.NOT_FOUND, "资产或负债不存在");
        require(kind == null || kind.equals(result.get("kind")), "资产类别与事件不匹配"); return result;
    }
    private Map<String, Object> checkpoint(String entityId, String field, BigDecimal value, String asOf, String basis) {
        return map("id", id(), "entity_id", entityId, "field", field, "value", num(value), "as_of", asOf, "basis", basis);
    }

    public synchronized Map<String, Object> createAccount(Map<String, Object> input) {
        String name = string(input.get("name"), "账户名称", 200, true);
        String currency = currency(input.get("currency"));
        String type = string(input.getOrDefault("type", "bank"), "账户类型", 40, true);
        BigDecimal balance = money(input.get("balance"), "余额", currency, "0", false);
        String basis = string(input.getOrDefault("basis", "opening"), "余额依据", 40, true);
        require(Arrays.asList("opening", "observation").contains(basis), "余额依据无效");
        require(balance.signum() == 0 || input.get("as_of") != null, "非零余额必须有截至时间");
        String asOf = input.get("as_of") == null ? EPOCH : timestamp(input.get("as_of")); past(asOf);
        String accountId = "account_" + id();
        Map<String, Object> result = map("id", accountId, "name", name, "type", type, "currency", currency, "created_at", now(),
                "initial", checkpoint(accountId, "balance", balance, asOf, basis));
        String requestKey=requestKey(input,"account");AtomicReference<Map<String,Object>> saved=new AtomicReference<>(result);
        store.mutate(all -> {
            Map<String,Object> previous=replayEntity(all,input,"accounts",requestKey);if(previous!=null){saved.set(previous);return;}
            expected(all, input); collection(all, "accounts").put(accountId, result);rememberEntity(all,input,requestKey,accountId);bump(all, "revision");
        });
        return accountView(saved.get(), projectCurrent().get(text(saved.get(),"id")));
    }

    public synchronized Map<String, Object> createAsset(Map<String, Object> input) {
        String name = string(input.get("name"), "资产名称", 200, true);
        String kind = string(input.get("kind"), "资产类别", 40, true);
        require(Arrays.asList("position", "manual", "liability").contains(kind), "资产类别必须是 position、manual 或 liability");
        String category = string(input.getOrDefault("category", kind), "资产分类", 60, true);
        String currency = currency(input.get("currency"));
        String basis = string(input.getOrDefault("basis", "opening"), "资产依据", 40, true);
        require(Arrays.asList("opening", "observation").contains(basis), "资产依据无效");
        String field = "position".equals(kind) ? "quantity" : "value";
        BigDecimal value = "position".equals(kind) ? number(input.get("quantity"), "数量", "0", false)
                : money(input.getOrDefault("value", input.get("balance")), "金额", currency, "0", false);
        require(value.signum() == 0 || input.get("as_of") != null, "非零持仓/估值/负债必须有截至时间");
        String asOf = input.get("as_of") == null ? EPOCH : timestamp(input.get("as_of")); past(asOf);
        String symbol = string(input.get("symbol"), "标的代码", 40, false);
        if (!symbol.isEmpty() && Arrays.asList("stock", "etf", "a-share", "a_share").contains(category)) {
            try { symbol = QuoteProvider.normalizeSymbol(symbol); } catch (IllegalArgumentException e) { require(false, e.getMessage()); }
            require("CNY".equals(currency), "A 股/场内 ETF 的原币种必须为 CNY");
        }
        String price = input.get("price") == null || "".equals(input.get("price")) ? null : num(number(input.get("price"), "价格", null, true));
        String assetId = "asset_" + id();
        Map<String, Object> result = map("id", assetId, "name", name, "kind", kind, "category", category, "currency", currency,
                "account_id", input.get("account_id"), "symbol", symbol.isEmpty() ? null : symbol, "created_at", now(),
                "initial", checkpoint(assetId, field, value, asOf, basis));
        if (price != null) result.put("initial_price", map("price", price, "as_of", asOf, "source", "manual", "status", "manual", "valuation_method", "manual"));
        String requestKey=requestKey(input,"asset");AtomicReference<Map<String,Object>> saved=new AtomicReference<>(result);
        store.mutate(all -> {
            Map<String,Object> previous=replayEntity(all,input,"assets",requestKey);if(previous!=null){saved.set(previous);return;}
            expected(all, input);
            if ("position".equals(kind)) require(currency.equals(account(all, input.get("account_id")).get("currency")), "持仓币种必须与所属账户一致；可为外币持仓创建单独账户");
            else if (input.get("account_id") != null && !"".equals(input.get("account_id"))) account(all, input.get("account_id"));
            collection(all, "assets").put(assetId, result);rememberEntity(all,input,requestKey,assetId);bump(all, "revision");
        });
        return assetView(saved.get(), projectCurrent().get(text(saved.get(),"id")));
    }

    private Map<String, Object> normalize(Map<String, Object> input) {
        require(FIELDS.containsAll(input.keySet()), "财务事件存在未知字段");
        String kind = string(input.get("type"), "事件类型", 50, true);
        require(TYPES.contains(kind), "财务事件类型无效");
        String occurred = timestamp(input.getOrDefault("occurred_at", now())); past(occurred);
        Map<String, Object> result = new TreeMap<>(); result.put("type", kind); result.put("occurred_at", occurred);
        for (String key : FIELDS) {
            if (Arrays.asList("type", "occurred_at", "expected_revision").contains(key)) continue;
            if (input.get(key) == null || "".equals(input.get(key))) continue;
            result.put(key, NUMBERS.contains(key) ? num(number(input.get(key), key, null, false)) : string(input.get(key), key, "note".equals(key) ? 2000 : 100, true));
        }
        result.putIfAbsent("source", "manual"); return result;
    }
    private String dedup(Map<String, Object> event) {
        if (event.get("idempotency_key") != null) return "request:" + event.get("idempotency_key");
        if (event.get("external_id") != null) return "external:" + hash(Arrays.asList(event.get("source"), event.get("account_id"), event.get("account_id") == null ? event.get("asset_id") : null, event.get("external_id")));
        return "content:" + hash(event);
    }
    private static void posting(List<Map<String, Object>> result, Map<String, Object> entity, String field, BigDecimal delta) {
        result.add(map("entity_id", entity.get("id"), "field", field, "delta", num(delta), "currency", entity.get("currency")));
    }
    private static BigDecimal amount(Map<String, Object> event, String key, String currency, String fallback, boolean positive) {
        return money(event.get(key), key, currency, fallback, positive);
    }
    private Map<String, Object> prepare(Map<String, Map<String, Map<String, Object>>> all, Map<String, Object> event) {
        String kind = text(event, "type");
        List<Map<String, Object>> postings = new ArrayList<>(), checkpoints = new ArrayList<>();
        Map<String, Object> cash = Arrays.asList("position_observation", "liability_observation", "valuation_adjustment").contains(kind) ? null : account(all, event.get("account_id"));
        String currency = cash == null ? null : text(cash, "currency");
        BigDecimal fee = cash == null ? ZERO : amount(event, "fee", currency, "0", false);
        if (Arrays.asList("income", "expense", "dividend", "interest").contains(kind)) {
            BigDecimal value = amount(event, "amount", currency, null, true);
            posting(postings, cash, "balance", "expense".equals(kind) ? value.negate().subtract(fee) : value.subtract(fee));
        } else if ("transfer".equals(kind)) {
            Map<String, Object> target = account(all, event.get("to_account_id"));
            require(!cash.get("id").equals(target.get("id")), "转账的两个账户必须不同");
            BigDecimal value = amount(event, "amount", currency, null, true);
            boolean same = currency.equals(target.get("currency"));
            BigDecimal targetValue = same ? value : amount(event, "target_amount", text(target, "currency"), null, true);
            require(!same || event.get("target_amount") == null || bd(event.get("target_amount")).compareTo(value) == 0, "同币种转账两侧金额必须一致，费用请单独填写");
            posting(postings, cash, "balance", value.negate().subtract(fee)); posting(postings, target, "balance", targetValue);
        } else if ("buy".equals(kind) || "sell".equals(kind)) {
            Map<String, Object> position = asset(all, event.get("asset_id"), "position");
            require(cash.get("id").equals(position.get("account_id")) && currency.equals(position.get("currency")), "交易持仓必须属于该账户及相同币种");
            BigDecimal quantity = number(event.get("quantity"), "数量", null, true), value;
            if (event.get("amount") != null) {
                value = amount(event, "amount", currency, null, true);
                if (event.get("price") != null) require(quantity.multiply(number(event.get("price"), "价格", null, true), PRECISION).subtract(value).abs().compareTo(BigDecimal.ONE.scaleByPowerOfTen(-scale(currency))) < 0, "数量、单价与成交金额不一致");
            } else {
                value = quantity.multiply(number(event.get("price"), "价格", null, true), PRECISION).setScale(scale(currency), RoundingMode.HALF_EVEN);
                require(value.signum() > 0, "成交金额必须大于零"); event.put("amount", num(value));
            }
            boolean buy = "buy".equals(kind);
            require(buy || fee.compareTo(value) <= 0, "卖出费用不能大于成交金额");
            posting(postings, cash, "balance", buy ? value.negate().subtract(fee) : value.subtract(fee));
            posting(postings, position, "quantity", buy ? quantity : quantity.negate());
        } else if ("borrow".equals(kind) || "repay".equals(kind)) {
            Map<String, Object> liability = asset(all, event.get("liability_id"), "liability");
            require(currency.equals(liability.get("currency")), "借还款币种必须与负债一致");
            BigDecimal principal = amount(event, "amount", currency, null, true), interest = amount(event, "interest", currency, "0", false);
            boolean borrow = "borrow".equals(kind); require(!borrow || interest.signum() == 0, "借款利息请通过支出或还款单独记录");
            posting(postings, cash, "balance", borrow ? principal.subtract(fee) : principal.negate().subtract(interest).subtract(fee));
            posting(postings, liability, "value", borrow ? principal : principal.negate());
        } else if ("asset_purchase".equals(kind)) {
            Map<String, Object> bought = asset(all, event.get("asset_id"), "manual");
            require(currency.equals(bought.get("currency")), "购入资产币种必须与付款账户一致");
            BigDecimal value = amount(event, "amount", currency, null, true), loan = amount(event, "loan_amount", currency, "0", false);
            require(loan.compareTo(value) <= 0, "购入贷款不能超过资产购价");
            if (loan.signum() != 0) {
                Map<String, Object> liability = asset(all, event.get("liability_id"), "liability");
                require(currency.equals(liability.get("currency")), "购入贷款币种必须一致"); posting(postings, liability, "value", loan);
            }
            posting(postings, cash, "balance", value.subtract(loan).negate().subtract(fee)); posting(postings, bought, "value", value);
        } else if ("balance_observation".equals(kind)) {
            require(fee.signum() == 0, "观测余额不能同时记录费用");
            checkpoints.add(checkpoint(text(cash, "id"), "balance", amount(event, "amount", currency, null, false), text(event, "occurred_at"), "observation"));
        } else {
            Map<String, Object> entity = asset(all, event.getOrDefault("asset_id", event.get("liability_id")), null);
            if ("position_observation".equals(kind)) {
                require("position".equals(entity.get("kind")), "持仓观测需要金融持仓");
                checkpoints.add(checkpoint(text(entity, "id"), "quantity", number(event.get("quantity"), "数量", null, false), text(event, "occurred_at"), "observation"));
            } else {
                require(("liability_observation".equals(kind) ? "liability" : "manual").equals(entity.get("kind")), "观测/估值类型与资产不匹配");
                checkpoints.add(checkpoint(text(entity, "id"), "value", amount(event, "amount", text(entity, "currency"), null, false), text(event, "occurred_at"), "observation"));
            }
        }
        return map("postings", postings, "checkpoints", checkpoints);
    }

    private Map<String, Object> insert(Map<String, Map<String, Map<String, Object>>> all, Map<String, Object> event, String batchId) {
        Map<String, Object> details = prepare(all, event);
        String dedup = dedup(event), signature = hash(event);
        Map<String, Object> prior = collection(all, "dedup").get(dedup);
        if (prior != null) {
            Map<String, Object> previous = collection(all, "events").get(text(prior, "event_id"));
            if (previous != null && Boolean.TRUE.equals(previous.get("active"))) {
                if (signature.equals(prior.get("signature"))) {
                    Map<String, Object> duplicate = eventView(previous); duplicate.put("duplicate", true); return duplicate;
                }
                if (!previous.get("id").equals(event.get("supersedes_id"))) throw conflict("同一来源交易 ID/幂等键对应不同内容，请核对后更正");
            }
        }
        if (event.get("supersedes_id") != null) {
            Map<String, Object> previous = collection(all, "events").get(text(event, "supersedes_id"));
            if (previous == null || !Boolean.TRUE.equals(previous.get("active"))) throw conflict("要更正的有效事件不存在");
            previous.put("active", false);
            Map<String,Object> previousPrice = collection(all,"prices").get(text(previous,"id"));
            if (previousPrice != null) previousPrice.put("active",false);
            collection(all, "audit").put(id(), map("operation", "correction", "target_id", previous.get("id"), "created_at", now()));
        }
        String eventId = "event_" + id();
        Map<String, Object> stored = map("id", eventId, "payload", new LinkedHashMap<>(event), "occurred_at", event.get("occurred_at"), "type", event.get("type"),
                "created_at", now(), "seq", bump(all, "sequence"), "dedup_key", dedup, "batch_id", batchId, "active", true, "supersedes_id", event.get("supersedes_id"),
                "postings", details.get("postings"), "checkpoints", details.get("checkpoints"));
        collection(all, "events").put(eventId, stored); collection(all, "dedup").put(dedup, map("event_id", eventId, "signature", signature));
        if (Arrays.asList("buy","sell","position_observation").contains(event.get("type")) && event.get("price") != null) {
            number(event.get("price"),"价格",null,true);
            collection(all,"prices").put(eventId,map("id",eventId,"asset_id",event.get("asset_id"),"price",event.get("price"),
                    "as_of",event.get("occurred_at"),"source","position_observation".equals(event.get("type")) ? "manual" : "transaction",
                    "valuation_method","position_observation".equals(event.get("type")) ? "manual" : "transaction_reference","status","manual","active",true,"seq",stored.get("seq")));
        }
        Map<String, Object> result = eventView(stored); result.put("duplicate", false); return result;
    }

    public synchronized Map<String, Object> createEvent(Map<String, Object> input) {
        Map<String, Object> event = normalize(input);
        AtomicReference<Map<String, Object>> result = new AtomicReference<>();
        store.mutate(all -> {
            Map<String, Object> inserted = insert(all, event, null);
            if (!Boolean.TRUE.equals(inserted.get("duplicate"))) { expected(all,input);bump(all, "revision"); project(all, now(), true); }
            inserted.put("ledger_revision", revision(all, "revision")); result.set(inserted);
        });
        return result.get();
    }

    @SuppressWarnings("unchecked") private static Map<String, Object> eventView(Map<String, Object> stored) {
        Map<String, Object> result = new LinkedHashMap<>((Map<String, Object>) stored.get("payload"));
        for (String key : Arrays.asList("id", "created_at", "active", "batch_id", "supersedes_id")) result.put(key, stored.get(key)); return result;
    }
    @SuppressWarnings("unchecked") private static List<Map<String, Object>> rows(Object value) { return value == null ? new ArrayList<>() : (List<Map<String, Object>>) value; }
    @SuppressWarnings("unchecked") private static Map<String, Object> obj(Object value) { return (Map<String, Object>) value; }
    private static List<Map<String, Object>> activeEvents(Map<String, Map<String, Map<String, Object>>> all, String asOf) {
        List<Map<String, Object>> result = new ArrayList<>();
        for (Map<String, Object> event : collection(all, "events").values()) if (Boolean.TRUE.equals(event.get("active")) && compareTime(text(event, "occurred_at"), asOf) <= 0) result.add(event);
        result.sort((a, b) -> { int time = compareTime(text(a, "occurred_at"), text(b, "occurred_at")); return time != 0 ? time : Long.compare(((Number) a.get("seq")).longValue(), ((Number) b.get("seq")).longValue()); });
        return result;
    }
    private Map<String, Map<String, Object>> project(Map<String, Map<String, Map<String, Object>>> all, String asOf, boolean validate) {
        Map<String, Map<String, Object>> state = new LinkedHashMap<>();
        List<Map<String, Object>> entities = new ArrayList<>(collection(all, "accounts").values()); entities.addAll(collection(all, "assets").values());
        for (Map<String, Object> entity : entities) {
            Map<String, Object> initial = obj(entity.get("initial"));
            if (compareTime(text(initial, "as_of"), asOf) <= 0) state.put(text(entity, "id"), new LinkedHashMap<>(initial));
        }
        List<Map<String, Object>> events = activeEvents(all, asOf);
        for (Map<String, Object> event : events) for (Map<String, Object> checkpoint : rows(event.get("checkpoints"))) {
            String entityId = text(checkpoint, "entity_id"); Map<String, Object> previous = state.get(entityId);
            if (previous == null || compareTime(text(checkpoint, "as_of"), text(previous, "as_of")) >= 0) {
                Map<String, Object> current = new LinkedHashMap<>(checkpoint); current.put("checkpoint_event_id", event.get("id")); state.put(entityId, current);
            }
        }
        for (Map<String, Object> event : events) for (Map<String, Object> posting : rows(event.get("postings"))) {
            String entityId = text(posting, "entity_id"); Map<String, Object> current = state.get(entityId);
            if (current == null) continue;
            int time = compareTime(text(event, "occurred_at"), text(current, "as_of"));
            if (time < 0 || time == 0 && "observation".equals(current.get("basis"))) continue;
            BigDecimal value = bd(current.get("value")).add(bd(posting.get("delta")), PRECISION);
            if (validate && value.signum() < 0 && collection(all, "assets").containsKey(entityId)) throw conflict("交易会造成负持仓/负债/资产估值，请核对数量、时间及余额依据");
            current.put("value", num(value)); current.put("last_event_at", event.get("occurred_at"));
        }
        return state;
    }
    private Map<String, Map<String, Object>> projectCurrent() {
        long revision = revision("revision");
        if (cachedState == null || cachedRevision != revision) {
            cachedState = project(store.snapshot(), now(), false); cachedRevision = revision; cachedAsOf = now();
        }
        return cachedState;
    }
    private static Map<String, Object> publicEntity(Map<String, Object> entity) {
        Map<String, Object> result = new LinkedHashMap<>(entity); result.remove("initial"); result.remove("initial_price"); return result;
    }
    private static Map<String, Object> accountView(Map<String, Object> account, Map<String, Object> state) {
        Map<String, Object> result = publicEntity(account);
        result.put("balance", state == null ? null : state.get("value"));
        result.put("basis", state == null ? null : state.get("basis")); result.put("as_of", state == null ? null : state.get("as_of"));
        result.put("checkpoint_id", state == null ? null : state.get("id")); return result;
    }
    private static Map<String, Object> assetView(Map<String, Object> asset, Map<String, Object> state) {
        Map<String, Object> result = publicEntity(asset);
        result.put("position".equals(asset.get("kind")) ? "quantity" : "value", state == null ? null : state.get("value"));
        result.put("basis", state == null ? null : state.get("basis")); result.put("as_of", state == null ? null : state.get("as_of"));
        result.put("checkpoint_id", state == null ? null : state.get("id")); return result;
    }
    private static List<Map<String, Object>> slice(List<Map<String, Object>> rows, int limit, int offset) {
        require(limit > 0 && limit <= 100 && offset >= 0, "分页参数无效");
        return new ArrayList<>(rows.subList(Math.min(offset, rows.size()), Math.min(rows.size(), offset + limit)));
    }
    private Map<String, Object> page(List<Map<String, Object>> rows, int limit, int offset) {
        return map("items", slice(rows, limit, offset), "total", rows.size(), "limit", limit, "offset", offset, "ledger_revision", revision("revision"));
    }
    public synchronized Map<String, Object> listAccounts(int limit, int offset) {
        List<Map<String, Object>> items = new ArrayList<>(); Map<String, Map<String, Object>> state = projectCurrent();
        for (Map<String, Object> item : store.list("finance_accounts")) items.add(accountView(item, state.get(text(item, "id")))); return page(items, limit, offset);
    }
    public synchronized Map<String, Object> listAssets(int limit, int offset) {
        List<Map<String, Object>> items = new ArrayList<>(); Map<String, Map<String, Object>> state = projectCurrent();
        for (Map<String, Object> item : store.list("finance_assets")) items.add(assetView(item, state.get(text(item, "id")))); return page(items, limit, offset);
    }
    public synchronized Map<String, Object> listEvents(int limit, int offset, boolean includeInactive) {
        List<Map<String, Object>> items = new ArrayList<>();
        for (Map<String, Object> item : store.list("finance_events")) if (includeInactive || Boolean.TRUE.equals(item.get("active"))) items.add(item);
        items.sort((a, b) -> { int time = compareTime(text(b, "occurred_at"), text(a, "occurred_at")); return time != 0 ? time : Long.compare(((Number) b.get("seq")).longValue(), ((Number) a.get("seq")).longValue()); });
        List<Map<String, Object>> selected = new ArrayList<>(); for (Map<String, Object> item : slice(items, limit, offset)) selected.add(eventView(item));
        return map("items", selected, "total", items.size(), "limit", limit, "offset", offset, "ledger_revision", revision("revision"));
    }

    /** CSV parser supports quoted commas, escaped quotes and embedded newlines. */
    private static List<List<String>> parseCsv(String content) {
        List<List<String>> result = new ArrayList<>(); List<String> row = new ArrayList<>();
        StringBuilder cell = new StringBuilder(); boolean quoted = false, closed = false;
        for (int index=0;index<content.length();index++) {
            char character=content.charAt(index);
            if (quoted) {
                if (character=='"') {
                    if (index+1<content.length() && content.charAt(index+1)=='"') {cell.append('"');index++;}
                    else {quoted=false;closed=true;}
                } else cell.append(character);
            } else if (character=='"') {
                require(cell.length()==0 && !closed,"CSV 引号位置无效");quoted=true;
            } else if (character==',' || character=='\r' || character=='\n') {
                row.add(cell.toString());cell.setLength(0);closed=false;
                if (character!=',') {
                    if (character=='\r' && index+1<content.length() && content.charAt(index+1)=='\n')index++;
                    if (row.size()!=1 || !row.get(0).trim().isEmpty())result.add(row);row=new ArrayList<>();
                }
            } else {require(!closed || Character.isWhitespace(character),"CSV 引号结束后存在非法内容"); if(!closed)cell.append(character);}
        }
        require(!quoted,"CSV 引号未闭合");
        if(cell.length()>0 || !row.isEmpty() || closed){row.add(cell.toString());result.add(row);}
        return result;
    }

    public synchronized Map<String,Object> previewImport(Map<String,Object> input) {
        String source=string(input.getOrDefault("source","manual-csv"),"导入来源",100,true);
        require(input.get("csv_text") instanceof String,"CSV 必须是文本");
        String content=(String)input.get("csv_text");require(content.getBytes(StandardCharsets.UTF_8).length<=2*1024*1024,"CSV 最多 2 MB");
        if(content.startsWith("\ufeff"))content=content.substring(1);
        List<List<String>> csv=parseCsv(content);require(csv.size()>1 && csv.size()<=5001,"CSV 必须包含 1 到 5000 条记录");
        List<String> headers=csv.get(0);require(new HashSet<>(headers).size()==headers.size() && FIELDS.containsAll(headers) && headers.contains("type"),"CSV 表头无效，请使用支持的财务事件字段");
        Map<String,Map<String,Map<String,Object>>> all=store.snapshot();List<Map<String,Object>> rows=new ArrayList<>();Map<String,String> seen=new HashMap<>();
        for(int index=1;index<csv.size();index++) {
            Map<String,Object> result=map("line",index+1,"status","new","message","");
            try {
                require(csv.get(index).size()==headers.size(),"列数与表头不一致");Map<String,Object> raw=new LinkedHashMap<>();
                for(int column=0;column<headers.size();column++)if(!csv.get(index).get(column).trim().isEmpty())raw.put(headers.get(column),csv.get(index).get(column).trim());
                raw.put("source",source);Map<String,Object> event=normalize(raw);prepare(all,event);
                String key=dedup(event),signature=hash(event);
                if(seen.containsKey(key)) {if(!signature.equals(seen.get(key)))throw conflict("批次中相同交易 ID 对应不同内容");result.put("status","duplicate");}
                else {
                    Map<String,Object> previous=collection(all,"dedup").get(key);
                    if(previous!=null) {
                        Map<String,Object> stored=collection(all,"events").get(text(previous,"event_id"));
                        if(stored!=null && Boolean.TRUE.equals(stored.get("active"))) {
                            if(signature.equals(previous.get("signature")))result.put("status","duplicate");
                            else if(!stored.get("id").equals(event.get("supersedes_id")))throw conflict("同一来源交易 ID 对应不同内容");
                        }
                    }
                }
                seen.put(key,signature);result.put("event",event);
            } catch(ResponseStatusException exception) {result.put("status",exception.getStatus()==HttpStatus.CONFLICT ? "conflict" : "error");result.put("message",exception.getReason());}
            rows.add(result);
        }
        String fingerprint=hash(Arrays.asList(source,rows));
        for(Map<String,Object> previous:store.list("finance_imports"))if(fingerprint.equals(previous.get("fingerprint")))return importView(previous,true);
        String importId="import_"+id();Map<String,Object> batch=map("id",importId,"source",source,"fingerprint",fingerprint,"rows",rows,"status","preview","created_at",now(),"committed_at",null,"reverted_at",null);
        store.put("finance_imports",importId,batch);return importView(batch,true);
    }
    private static Map<String,Object> importView(Map<String,Object> batch,boolean includeRows) {
        Map<String,Object> counts=map("new",0,"duplicate",0,"conflict",0,"error",0);
        for(Map<String,Object> row:rows(batch.get("rows")))counts.put(text(row,"status"),((Number)counts.get(text(row,"status"))).intValue()+1);
        Map<String,Object> result=publicEntity(batch);result.remove("fingerprint");if(!includeRows)result.remove("rows");
        result.put("counts",counts);result.put("valid",((Number)counts.get("conflict")).intValue()==0 && ((Number)counts.get("error")).intValue()==0);return result;
    }
    public synchronized Map<String,Object> listImports(int limit,int offset) {
        List<Map<String,Object>> result=store.list("finance_imports");result.sort((a,b)->compareTime(text(b,"created_at"),text(a,"created_at")));
        List<Map<String,Object>> items=new ArrayList<>();for(Map<String,Object> batch:slice(result,limit,offset))items.add(importView(batch,false));
        return map("items",items,"total",result.size(),"limit",limit,"offset",offset);
    }
    public synchronized Map<String,Object> commitImport(String importId) {
        AtomicReference<Map<String,Object>> result=new AtomicReference<>();
        store.mutate(all->{
            Map<String,Object> batch=collection(all,"imports").get(importId);
            if(batch==null)throw new ResponseStatusException(HttpStatus.NOT_FOUND,"导入批次不存在");
            if("committed".equals(batch.get("status"))){Map<String,Object> view=importView(batch,true);view.put("duplicate",true);result.set(view);return;}
            if(!"preview".equals(batch.get("status")))throw conflict("已撤销的批次不能再次提交，请重新预览");
            if(!Boolean.TRUE.equals(importView(batch,false).get("valid")))throw conflict("批次存在错误或冲突，请重新预览");
            int inserted=0;
            for(Map<String,Object> row:rows(batch.get("rows")))if(!Boolean.TRUE.equals(insert(all,new TreeMap<>(obj(row.get("event"))),importId).get("duplicate")))inserted++;
            if(inserted>0){bump(all,"revision");project(all,now(),true);}
            batch.put("status","committed");batch.put("committed_at",now());Map<String,Object> view=importView(batch,true);
            view.put("inserted",inserted);view.put("duplicate",false);view.put("ledger_revision",revision(all,"revision"));result.set(view);
        });return result.get();
    }
    public synchronized Map<String,Object> revertImport(String importId) {
        AtomicReference<Map<String,Object>> result=new AtomicReference<>();
        store.mutate(all->{
            Map<String,Object> batch=collection(all,"imports").get(importId);
            if(batch==null)throw new ResponseStatusException(HttpStatus.NOT_FOUND,"导入批次不存在");
            if("reverted".equals(batch.get("status"))){Map<String,Object> view=importView(batch,true);view.put("duplicate",true);result.set(view);return;}
            if(!"committed".equals(batch.get("status")))throw conflict("只能撤销已提交的批次");
            for(Map<String,Object> event:collection(all,"events").values())if(Boolean.TRUE.equals(event.get("active")) && event.get("supersedes_id")!=null){
                Map<String,Object> previous=collection(all,"events").get(text(event,"supersedes_id"));
                if(previous!=null && importId.equals(previous.get("batch_id")) && !importId.equals(event.get("batch_id")))throw conflict("该批次已有后续更正，请先核对更正关系");
            }
            for(Map<String,Object> event:collection(all,"events").values())if(importId.equals(event.get("batch_id"))){
                event.put("active",false);Map<String,Object> price=collection(all,"prices").get(text(event,"id"));if(price!=null)price.put("active",false);
                if(event.get("supersedes_id")!=null){
                    Map<String,Object> previous=collection(all,"events").get(text(event,"supersedes_id"));
                    if(previous!=null && !importId.equals(previous.get("batch_id"))) {
                        previous.put("active",true);Map<String,Object> previousPrice=collection(all,"prices").get(text(event,"supersedes_id"));if(previousPrice!=null)previousPrice.put("active",true);
                    }
                }
            }
            collection(all,"dedup").clear();
            for(Map<String,Object> event:collection(all,"events").values())if(Boolean.TRUE.equals(event.get("active")))collection(all,"dedup").put(text(event,"dedup_key"),map("event_id",event.get("id"),"signature",hash(event.get("payload"))));
            collection(all,"audit").put(id(),map("operation","revert_import","target_id",importId,"created_at",now()));
            bump(all,"revision");project(all,now(),true);batch.put("status","reverted");batch.put("reverted_at",now());
            Map<String,Object> view=importView(batch,true);view.put("ledger_revision",revision(all,"revision"));result.set(view);
        });return result.get();
    }

    public synchronized Map<String,Object> setRate(Map<String,Object> input) {
        String base=currency(input.get("base")),quote=currency(input.get("quote"));require(!base.equals(quote),"汇率的两个币种必须不同");
        BigDecimal rate=number(input.get("rate"),"汇率",null,true);String asOf=timestamp(input.getOrDefault("as_of",now()));past(asOf);
        Map<String,Object> result=map("id","rate_"+id(),"base",base,"quote",quote,"rate",num(rate),"as_of",asOf,"source",string(input.getOrDefault("source","manual"),"汇率来源",100,true),"created_at",now());
        store.mutate(all->{result.put("seq",bump(all,"quote_revision"));collection(all,"rates").put(text(result,"id"),result);});return result;
    }
    private static Map<String,Object> rate(List<Map<String,Object>> rates,String currency,String base,String asOf) {
        if(currency.equals(base))return map("base",currency,"quote",base,"rate","1","effective_rate","1","source","same_currency");
        Map<String,Object> selected=null;
        for(Map<String,Object> row:rates)if((currency.equals(row.get("base")) && base.equals(row.get("quote")) || base.equals(row.get("base")) && currency.equals(row.get("quote"))) && compareTime(text(row,"as_of"),asOf)<=0){
            if(selected==null || compareTime(text(row,"as_of"),text(selected,"as_of"))>0 || compareTime(text(row,"as_of"),text(selected,"as_of"))==0 && ((Number)row.getOrDefault("seq",0)).longValue()>=((Number)selected.getOrDefault("seq",0)).longValue())selected=row;
        }
        if(selected==null)return null;Map<String,Object> result=new LinkedHashMap<>(selected);
        result.put("effective_rate",num(currency.equals(selected.get("base")) ? bd(selected.get("rate")) : BigDecimal.ONE.divide(bd(selected.get("rate")),PRECISION)));return result;
    }
    private static Map<String,Object> assetPrice(Map<String,Object> asset,List<Map<String,Object>> prices,List<Map<String,Object>> quotes,String asOf) {
        Map<String,Object> selected=null;
        if(asset.get("initial_price")!=null && compareTime(text(obj(asset.get("initial_price")),"as_of"),asOf)<=0)selected=new LinkedHashMap<>(obj(asset.get("initial_price")));
        for(Map<String,Object> price:prices)if(Boolean.TRUE.equals(price.get("active")) && asset.get("id").equals(price.get("asset_id")) && compareTime(text(price,"as_of"),asOf)<=0 && (selected==null || compareTime(text(price,"as_of"),text(selected,"as_of"))>0 || compareTime(text(price,"as_of"),text(selected,"as_of"))==0 && ((Number)price.getOrDefault("seq",0)).longValue()>=((Number)selected.getOrDefault("seq",0)).longValue()))selected=new LinkedHashMap<>(price);
        for(Map<String,Object> quote:quotes)if(asset.get("symbol")!=null && asset.get("symbol").equals(quote.get("symbol")) && asset.get("currency").equals(quote.get("currency")) && compareTime(text(quote,"market_time"),asOf)<=0 && (selected==null || compareTime(text(quote,"market_time"),text(selected,"as_of"))>=0)){
            selected=new LinkedHashMap<>(quote);selected.put("as_of",quote.get("market_time"));selected.put("valuation_method","market");
        }
        return selected;
    }
    private static BigDecimal converted(BigDecimal value,String currency,String base,String asOf,String entityId,List<Map<String,Object>> rates,List<Map<String,Object>> missing,List<Map<String,Object>> warnings,Map<String,Object> references) {
        Map<String,Object> rate=rate(rates,currency,base,asOf);
        if(rate==null){missing.add(map("id",entityId,"reason","missing_exchange_rate","currency",currency));return null;}
        references.put(currency,rate);
        if(rate.get("as_of")!=null && Duration.between(Instant.parse(text(rate,"as_of")),Instant.parse(asOf)).toDays()>7)warnings.add(map("id",entityId,"reason","stale_exchange_rate"));
        return value.multiply(bd(rate.get("effective_rate")),PRECISION);
    }
    private static void add(Map<String,BigDecimal> values,String key,BigDecimal value){values.put(key,values.getOrDefault(key,ZERO).add(value,PRECISION));}
    private static Map<String,Object> displayed(Map<String,BigDecimal> values,String currency){Map<String,Object> result=new LinkedHashMap<>();for(Map.Entry<String,BigDecimal> entry:values.entrySet())result.put(entry.getKey(),currency==null ? num(entry.getValue()) : entry.getValue().setScale(scale(currency),RoundingMode.HALF_EVEN).toPlainString());return result;}

    public synchronized Map<String,Object> summary(String baseCurrency,String suppliedAsOf) {
        String base=currency(baseCurrency),asOf=suppliedAsOf==null || suppliedAsOf.isEmpty() ? now() : timestamp(suppliedAsOf);past(asOf);
        Map<String,Map<String,Object>> state=suppliedAsOf==null || suppliedAsOf.isEmpty() ? projectCurrent() : project(store.snapshot(),asOf,false);
        List<Map<String,Object>> accountRows=store.list("finance_accounts"),assetRows=store.list("finance_assets"),rates=store.list("finance_rates"),prices=store.list("finance_prices"),quotes=store.list("finance_quotes");
        List<Map<String,Object>> accounts=new ArrayList<>(),assets=new ArrayList<>(),missing=new ArrayList<>(),warnings=new ArrayList<>();
        Map<String,Object> references=new LinkedHashMap<>();Map<String,BigDecimal> categories=new LinkedHashMap<>(),currencies=new LinkedHashMap<>();
        BigDecimal knownAssets=ZERO,knownLiabilities=ZERO;int known=0;
        for(Map<String,Object> account:accountRows){
            String accountId=text(account,"id"),currency=text(account,"currency");Map<String,Object> item=accountView(account,state.get(accountId));
            BigDecimal baseValue=null;
            if(item.get("balance")==null)missing.add(map("id",accountId,"reason","missing_balance_basis"));
            else {
                BigDecimal value=bd(item.get("balance"));add(currencies,currency,value);
                baseValue=converted(value,currency,base,asOf,accountId,rates,missing,warnings,references);
                if(baseValue!=null){known++;if(baseValue.signum()<0){knownLiabilities=knownLiabilities.subtract(baseValue);add(categories,"overdraft",baseValue.negate());}else{knownAssets=knownAssets.add(baseValue);add(categories,"cash",baseValue);}}
            }
            item.put("base_value",baseValue==null?null:num(baseValue));accounts.add(item);
        }
        for(Map<String,Object> entity:assetRows){
            String assetId=text(entity,"id"),currency=text(entity,"currency"),kind=text(entity,"kind");Map<String,Object> item=assetView(entity,state.get(assetId));BigDecimal value=null;
            if(state.get(assetId)==null)missing.add(map("id",assetId,"reason","missing_asset_basis"));
            else if("position".equals(kind)){
                BigDecimal quantity=bd(state.get(assetId).get("value"));Map<String,Object> quote=assetPrice(entity,prices,quotes,asOf);item.put("quote",quote);
                if(quantity.signum()==0)value=ZERO;
                else if(quote==null)missing.add(map("id",assetId,"reason","missing_price"));
                else {
                    value=quantity.multiply(bd(quote.get("price")),PRECISION);
                    boolean stale=Duration.between(Instant.parse(text(quote,"as_of")),Instant.parse(asOf)).compareTo(Duration.ofDays(1))>0 || !"valid".equals(quote.get("status"));
                    item.put("stale",stale);if(stale)warnings.add(map("id",assetId,"reason","stale_or_manual_price"));
                    if("needs_reconciliation".equals(quote.get("status")))warnings.add(map("id",assetId,"reason","possible_corporate_action","requires_reconciliation",true));
                }
            } else {value=bd(state.get(assetId).get("value"));item.put("valuation_method","manual");}
            if(value!=null && value.signum()<0){missing.add(map("id",assetId,"reason","needs_reconciliation"));value=null;}
            BigDecimal baseValue=value==null?null:converted(value,currency,base,asOf,assetId,rates,missing,warnings,references);
            item.put("value",value==null?null:num(value));item.put("base_value",baseValue==null?null:num(baseValue));
            if(value!=null)add(currencies,currency,"liability".equals(kind)?value.negate():value);
            if(baseValue!=null){known++;if("liability".equals(kind))knownLiabilities=knownLiabilities.add(baseValue);else{knownAssets=knownAssets.add(baseValue);add(categories,text(entity,"category"),baseValue);}}
            assets.add(item);
        }
        boolean complete=missing.isEmpty();BigDecimal net=knownAssets.subtract(knownLiabilities);String assetsText=knownAssets.setScale(scale(base),RoundingMode.HALF_EVEN).toPlainString(),liabilitiesText=knownLiabilities.setScale(scale(base),RoundingMode.HALF_EVEN).toPlainString(),netText=net.setScale(scale(base),RoundingMode.HALF_EVEN).toPlainString();
        return map("base_currency",base,"as_of",asOf,"ledger_revision",revision("revision"),"quote_revision",revision("quote_revision"),"complete",complete,"fresh",complete && warnings.isEmpty(),
                "total_assets",complete?assetsText:null,"total_liabilities",complete?liabilitiesText:null,"net_worth",complete?netText:null,
                "known_total_assets",assetsText,"known_total_liabilities",liabilitiesText,"known_net_worth",netText,"missing",missing,"warnings",warnings,
                "accounts",accounts,"assets",assets,"by_category",displayed(categories,base),"by_currency",displayed(currencies,null),"exchange_rates",references,
                "cash_flow",cashFlow(base,asOf,rates,suppliedAsOf==null || suppliedAsOf.isEmpty()),"coverage",map("known",known,"total",accounts.size()+assets.size()));
    }
    public Map<String,Object> summary(){return summary("CNY",null);}
    private Map<String,Object> cashFlow(String base,String asOf,List<Map<String,Object>> rates,boolean current) {
        String cacheKey=base+":"+revision("revision")+":"+revision("quote_revision");
        if(current && cashflowCache.containsKey(cacheKey))return new LinkedHashMap<>(cashflowCache.get(cacheKey));
        List<String> keys=Arrays.asList("income","expense","investment_income","fees","loan_principal","external_flow");
        Map<String,BigDecimal> totals=new LinkedHashMap<>();for(String key:keys)totals.put(key,ZERO);
        Map<String,Map<String,BigDecimal>> perCurrency=new LinkedHashMap<>();List<Map<String,Object>> missing=new ArrayList<>();Map<String,String> currencies=new HashMap<>();
        for(Map<String,Object> account:store.list("finance_accounts"))currencies.put(text(account,"id"),text(account,"currency"));
        for(Map<String,Object> row:store.list("finance_events")){
            if(!Boolean.TRUE.equals(row.get("active")) || compareTime(text(row,"occurred_at"),asOf)>0)continue;Map<String,Object> event=obj(row.get("payload"));
            if(event.get("account_id")==null)continue;String currency=currencies.get(text(event,"account_id")),kind=text(event,"type");
            Map<String,BigDecimal> values=new LinkedHashMap<>();for(String key:keys)values.put(key,ZERO);
            BigDecimal amount=bd(event.getOrDefault("amount","0")),fee=bd(event.getOrDefault("fee","0"));values.put("fees",fee);values.put("expense",fee);
            if("income".equals(kind)){values.put("income",amount);values.put("external_flow",amount);}
            else if("expense".equals(kind)){add(values,"expense",amount);values.put("external_flow",amount.negate());}
            else if("dividend".equals(kind) || "interest".equals(kind))values.put("investment_income",amount);
            else if("repay".equals(kind)){add(values,"expense",bd(event.getOrDefault("interest","0")));values.put("loan_principal",amount.negate());}
            else if("borrow".equals(kind))values.put("loan_principal",amount);
            else if("asset_purchase".equals(kind))values.put("loan_principal",bd(event.getOrDefault("loan_amount","0")));
            add(values,"external_flow","expense".equals(kind)?fee.negate():values.get("expense").negate());
            Map<String,BigDecimal> original=perCurrency.computeIfAbsent(currency,key->{Map<String,BigDecimal> initial=new LinkedHashMap<>();for(String field:keys)initial.put(field,ZERO);return initial;});
            Map<String,Object> exchange=rate(rates,currency,base,text(row,"occurred_at"));boolean affected=false;
            for(String key:keys){BigDecimal value=values.get(key);add(original,key,value);affected|=value.signum()!=0;if(exchange!=null)add(totals,key,value.multiply(bd(exchange.get("effective_rate")),PRECISION));}
            if(exchange==null && affected)missing.add(map("id",row.get("id"),"reason","missing_historical_exchange_rate","currency",currency));
        }
        Map<String,Object> result=displayed(totals,null);if(!missing.isEmpty())for(String key:keys)result.put(key,null);
        Map<String,Object> original=new LinkedHashMap<>();for(Map.Entry<String,Map<String,BigDecimal>> entry:perCurrency.entrySet())original.put(entry.getKey(),displayed(entry.getValue(),null));
        result.put("known",displayed(totals,null));result.put("by_currency",original);result.put("complete",missing.isEmpty());result.put("missing",missing);result.put("period","all_recorded_events");result.put("investment_return",null);
        if(current){cashflowCache.clear();cashflowCache.put(cacheKey,result);}return result;
    }
    public synchronized Map<String,Object> saveSnapshot(String baseCurrency) {
        Map<String,Object> summary=summary(baseCurrency,null);Map<String,Object> reference=new LinkedHashMap<>(summary);reference.remove("as_of");String fingerprint=hash(reference);
        AtomicReference<Map<String,Object>> result=new AtomicReference<>();
        store.mutate(all->{
            if(((Number)summary.get("ledger_revision")).longValue()!=revision(all,"revision") || ((Number)summary.get("quote_revision")).longValue()!=revision(all,"quote_revision"))throw conflict("估值在保存期间变化，请刷新后重试");
            for(Map<String,Object> previous:collection(all,"snapshots").values())if(fingerprint.equals(previous.get("fingerprint"))){result.set(map("id",previous.get("id"),"data",previous.get("data"),"duplicate",true));return;}
            String snapshotId="snapshot_"+id();collection(all,"snapshots").put(snapshotId,map("id",snapshotId,"fingerprint",fingerprint,"as_of",summary.get("as_of"),"ledger_revision",summary.get("ledger_revision"),"quote_revision",summary.get("quote_revision"),"data",summary));result.set(map("id",snapshotId,"data",summary,"duplicate",false));
        });return result.get();
    }
    public synchronized Map<String,Object> listSnapshots(int limit,int offset) {
        List<Map<String,Object>> snapshots=store.list("finance_snapshots");snapshots.sort((a,b)->{int time=compareTime(text(b,"as_of"),text(a,"as_of"));return time==0?text(b,"id").compareTo(text(a,"id")):time;});
        List<Map<String,Object>> selected=slice(snapshots,limit,offset);for(Map<String,Object> item:selected)item.remove("fingerprint");
        return map("items",selected,"total",snapshots.size(),"limit",limit,"offset",offset);
    }
    public synchronized Map<String,Object> refreshQuotes() {
        List<Map<String,Object>> assets=store.list("finance_assets");Set<String> symbols=new LinkedHashSet<>();List<String> unsupported=new ArrayList<>();
        for(Map<String,Object> asset:assets)if("position".equals(asset.get("kind"))){
            try {if(!"CNY".equals(asset.get("currency")))throw new IllegalArgumentException();symbols.add(QuoteProvider.normalizeSymbol(text(asset,"symbol")));}
            catch(IllegalArgumentException exception){unsupported.add(text(asset,"id"));}
        }
        require(symbols.size()<=100,"每次最多刷新 100 个标的；请分批管理持仓");Map<String,Map<String,Object>> fetched;
        try {fetched=quotes.fetch(new ArrayList<>(symbols));}catch(RuntimeException exception){fetched=new LinkedHashMap<>();}
        final Map<String,Map<String,Object>> response=fetched;List<Map<String,Object>> updated=new ArrayList<>(),failed=new ArrayList<>();
        store.mutate(all->{
            boolean changed=false;
            for(String symbol:symbols){
                Map<String,Object> previous=collection(all,"quotes").get(symbol),quote=response.get(symbol);
                try {
                    require(quote!=null && "CNY".equals(quote.get("currency")),"行情字段无效");BigDecimal price=number(quote.get("price"),"行情价格",null,true);
                    String marketTime=timestamp(quote.get("market_time"));past(marketTime);require(previous==null || compareTime(marketTime,text(previous,"market_time"))>=0,"行情时间倒退");
                    String status="valid";
                    if(previous!=null && price.divide(bd(previous.get("price")),PRECISION).subtract(BigDecimal.ONE).abs().compareTo(new BigDecimal("0.4"))>0)status="needs_reconciliation";
                    if(previous!=null && "needs_reconciliation".equals(previous.get("status")))for(Map<String,Object> asset:assets)if(symbol.equals(asset.get("symbol"))){
                        boolean reconciled=false;for(Map<String,Object> event:collection(all,"events").values())if(Boolean.TRUE.equals(event.get("active")))for(Map<String,Object> checkpoint:rows(event.get("checkpoints")))if(asset.get("id").equals(checkpoint.get("entity_id")) && compareTime(text(checkpoint,"as_of"),text(previous,"market_time"))>=0)reconciled=true;
                        if(!reconciled)status="needs_reconciliation";
                    }
                    Object close=quote.get("previous_close");if(close!=null)close=num(number(close,"昨收",null,true));
                    Map<String,Object> stored=map("symbol",symbol,"price",num(price),"currency","CNY","market_time",marketTime,"collected_at",now(),"source","Tencent Finance","status",status,"previous_close",close);
                    collection(all,"quotes").put(symbol,stored);updated.add(map("symbol",symbol,"price",num(price),"market_time",marketTime,"status",status));changed=true;
                }catch(RuntimeException exception){
                    failed.add(map("symbol",symbol,"reason","quote_unavailable","retained_previous",previous!=null));
                    if(previous!=null && !"needs_reconciliation".equals(previous.get("status"))){previous.put("status","stale");changed=true;}
                }
            }
            if(changed)bump(all,"quote_revision");
        });return map("updated",updated,"failed",failed,"unsupported",unsupported,"collected_at",now(),"quote_revision",revision("quote_revision"));
    }
}
