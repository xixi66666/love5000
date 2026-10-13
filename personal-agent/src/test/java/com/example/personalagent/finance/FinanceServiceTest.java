package com.example.personalagent.finance;

import com.example.personalagent.storage.DocumentDao;
import com.example.personalagent.storage.Store;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.TransactionDefinition;
import org.springframework.transaction.support.SimpleTransactionStatus;
import org.springframework.web.server.ResponseStatusException;

import java.time.Instant;
import java.util.*;
import java.util.concurrent.atomic.AtomicReference;

import static com.example.personalagent.Api.*;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

/** All money and holdings are constructed; neither credentials nor market network are used. */
class FinanceServiceTest {
    private static final Instant NOW=Instant.parse("2026-10-13T09:00:00Z");
    private final Map<String,Map<String,Object>> documents=new LinkedHashMap<>();
    private DocumentDao dao;
    private PlatformTransactionManager manager;
    private FinanceService ledger;

    @BeforeEach void prepare() throws Exception {
        dao=mock(DocumentDao.class);manager=mock(PlatformTransactionManager.class);
        when(manager.getTransaction(any(TransactionDefinition.class))).thenAnswer(invocation->new SimpleTransactionStatus());
        when(dao.all()).thenAnswer(invocation->new ArrayList<>(documents.values()));
        doAnswer(invocation->{String collection=invocation.getArgument(0),id=invocation.getArgument(1),body=invocation.getArgument(2);
            documents.put(collection+":"+id,map("collection",collection,"id",id,"body",body));return null;}).when(dao).upsert(anyString(),anyString(),anyString());
        doAnswer(invocation->{documents.remove(invocation.getArgument(0)+":"+invocation.getArgument(1));return null;}).when(dao).delete(anyString(),anyString());
        ledger=new FinanceService(new Store(dao,new ObjectMapper(),manager),()->NOW,new QuoteProvider(url->{throw new IllegalStateException("测试不得联网");}));
    }
    private Map<String,Object> account(String balance){return account(balance,"CNY");}
    private Map<String,Object> account(String balance,String currency){return ledger.createAccount(map("name","构造账户","balance",balance,"currency",currency,"as_of","2026-10-01"));}
    private Map<String,Object> asset(String kind,Object... extras){Map<String,Object> input=map("name","构造资产","kind",kind,"currency","CNY");input.putAll(map(extras));return ledger.createAsset(input);}
    private Map<String,Object> event(String kind,Object... extras){Map<String,Object> input=map("type",kind,"occurred_at","2026-10-10T12:00:00+08:00");input.putAll(map(extras));return ledger.createEvent(input);}
    @SuppressWarnings("unchecked") private static Map<String,Object> obj(Object value){return (Map<String,Object>)value;}
    @SuppressWarnings("unchecked") private static List<Map<String,Object>> rows(Object value){return (List<Map<String,Object>>)value;}
    private String balance(String accountId){return text(rows(ledger.listAccounts(100,0).get("items")).stream().filter(row->accountId.equals(row.get("id"))).findFirst().get(),"balance");}

    @Test void buySellMovesCashAndQuantityAndOnlyFeesAreExpenses() {
        Map<String,Object> cash=account("10000"),position=asset("position","account_id",cash.get("id"),"symbol","600519","category","stock");
        event("buy","account_id",cash.get("id"),"asset_id",position.get("id"),"quantity","100","price","10","fee","5");
        assertEquals("8995",balance(text(cash,"id")));assertEquals("9995.00",ledger.summary().get("net_worth"));assertEquals("5",obj(ledger.summary().get("cash_flow")).get("expense"));
        event("sell","occurred_at","2026-10-11","account_id",cash.get("id"),"asset_id",position.get("id"),"quantity","20","price","12","fee","2");
        assertEquals("9233",balance(text(cash,"id")));assertEquals("80",rows(ledger.listAssets(50,0).get("items")).get(0).get("quantity"));assertEquals("10193.00",ledger.summary().get("net_worth"));
        assertEquals("0",obj(ledger.summary().get("cash_flow")).get("income"));assertEquals("7",obj(ledger.summary().get("cash_flow")).get("expense"));assertNull(obj(ledger.summary().get("cash_flow")).get("investment_return"));
    }
    @Test void transferBorrowAndRepayHaveCorrectAssetsLiabilitiesAndIncome() {
        Map<String,Object> first=account("10000"),second=account("0"),debt=asset("liability");
        event("transfer","account_id",first.get("id"),"to_account_id",second.get("id"),"amount","5000");assertEquals("10000.00",ledger.summary().get("net_worth"));
        event("borrow","account_id",second.get("id"),"liability_id",debt.get("id"),"amount","20000");
        assertEquals("30000.00",ledger.summary().get("total_assets"));assertEquals("20000.00",ledger.summary().get("total_liabilities"));assertEquals("10000.00",ledger.summary().get("net_worth"));
        event("repay","occurred_at","2026-10-11","account_id",second.get("id"),"liability_id",debt.get("id"),"amount","1000","interest","100");
        assertEquals("9900.00",ledger.summary().get("net_worth"));assertEquals("19000.00",ledger.summary().get("total_liabilities"));
        assertEquals("0",obj(ledger.summary().get("cash_flow")).get("income"));assertEquals("100",obj(ledger.summary().get("cash_flow")).get("expense"));
    }
    @Test void propertyPurchaseDoesNotDoubleCountLoanOrDownPayment() {
        Map<String,Object> cash=account("3000"),property=asset("manual","category","property"),debt=asset("liability");
        event("asset_purchase","account_id",cash.get("id"),"asset_id",property.get("id"),"liability_id",debt.get("id"),"amount","10000","loan_amount","8000");
        assertEquals("1000",balance(text(cash,"id")));assertEquals("11000.00",ledger.summary().get("total_assets"));assertEquals("8000.00",ledger.summary().get("total_liabilities"));assertEquals("3000.00",ledger.summary().get("net_worth"));
        assertEquals("0",obj(ledger.summary().get("cash_flow")).get("expense"));
    }
    @Test void expensesIncomeAndDividendHaveDistinctCashFlow() {
        Map<String,Object> cash=account("0");event("income","account_id",cash.get("id"),"amount","100");event("expense","account_id",cash.get("id"),"amount","30");event("dividend","account_id",cash.get("id"),"amount","10");
        assertEquals("80.00",ledger.summary().get("net_worth"));Map<String,Object> flow=obj(ledger.summary().get("cash_flow"));
        assertEquals("100",flow.get("income"));assertEquals("30",flow.get("expense"));assertEquals("10",flow.get("investment_income"));assertEquals("70",flow.get("external_flow"));
    }
    @Test void exactDecimalAndMoneyScaleRejectFloatingOrInvalidInput() {
        Map<String,Object> cash=account("0");for(int index=0;index<3;index++)event("income","account_id",cash.get("id"),"amount","0.10","external_id",String.valueOf(index));
        assertEquals("0.3",balance(text(cash,"id")));assertEquals("0.30",ledger.summary().get("net_worth"));
        for(Object invalid:Arrays.asList(0.1,"NaN","Infinity","1e2","-1","0.001"))assertThrows(ResponseStatusException.class,()->event("income","account_id",cash.get("id"),"amount",invalid));
    }
    @Test void missingPricesOrRatesAreUnknownNotZeroOrOne() {
        Map<String,Object> cash=account("10","USD"),position=asset("position","account_id",cash.get("id"),"currency","USD","quantity","2","as_of","2026-10-01");
        assertNull(ledger.summary().get("net_worth"));assertFalse((Boolean)ledger.summary().get("complete"));assertEquals(2,rows(ledger.summary().get("missing")).size());
        ledger.setRate(map("base","USD","quote","CNY","rate","7","as_of","2026-10-01"));assertEquals("70.00",ledger.summary().get("known_net_worth"));assertNull(ledger.summary().get("net_worth"));
        event("position_observation","asset_id",position.get("id"),"quantity","2","price","5");assertEquals("140.00",ledger.summary().get("net_worth"));
    }
    @Test void crossCurrencyTransferRequiresBothAmountsAndActualRate() {
        Map<String,Object> cash=account("700"),foreign=account("0","USD");
        assertThrows(ResponseStatusException.class,()->event("transfer","account_id",cash.get("id"),"to_account_id",foreign.get("id"),"amount","700"));
        event("transfer","account_id",cash.get("id"),"to_account_id",foreign.get("id"),"amount","700","target_amount","100");
        assertEquals("0",balance(text(cash,"id")));assertEquals("100",balance(text(foreign,"id")));assertNull(ledger.summary().get("net_worth"));
        ledger.setRate(map("base","CNY","quote","USD","rate","0.125","as_of","2026-10-01"));assertEquals("800.00",ledger.summary().get("net_worth"));
    }
    @Test void overSellAndExcessiveRepayRollbackEntireMutation() {
        Map<String,Object> cash=account("10000"),position=asset("position","account_id",cash.get("id")),debt=asset("liability");
        assertThrows(ResponseStatusException.class,()->event("sell","account_id",cash.get("id"),"asset_id",position.get("id"),"quantity","1","price","10"));
        assertThrows(ResponseStatusException.class,()->event("repay","account_id",cash.get("id"),"liability_id",debt.get("id"),"amount","1"));
        assertEquals(0,ledger.listEvents(50,0,false).get("total"));assertEquals("10000",balance(text(cash,"id")));
        event("buy","occurred_at","2026-10-11","account_id",cash.get("id"),"asset_id",position.get("id"),"quantity","2","price","10");
        assertThrows(ResponseStatusException.class,()->event("sell","occurred_at","2026-10-10","account_id",cash.get("id"),"asset_id",position.get("id"),"quantity","1","price","10"));
        assertEquals(1,ledger.listEvents(50,0,false).get("total"));
    }
    @Test void externalIdScopeIncludesAccountAndConflictingContentFails() {
        Map<String,Object> first=account("0"),second=account("0");
        for(Map<String,Object> cash:Arrays.asList(first,second))assertFalse((Boolean)event("income","account_id",cash.get("id"),"amount","10","source","csv-bank","external_id","same-id").get("duplicate"));
        assertTrue((Boolean)event("income","account_id",first.get("id"),"amount","10","source","csv-bank","external_id","same-id").get("duplicate"));
        assertThrows(ResponseStatusException.class,()->event("income","account_id",first.get("id"),"amount","11","source","csv-bank","external_id","same-id"));assertEquals(2,ledger.listEvents(50,0,false).get("total"));
    }
    @Test void observationBatchRevertRestoresPriorCashCheckpointAndRealEvents() {
        Map<String,Object> cash=account("1000");event("income","occurred_at","2026-10-03","account_id",cash.get("id"),"amount","500");
        Map<String,Object> preview=ledger.previewImport(map("csv_text","type,occurred_at,account_id,amount,external_id\nbalance_observation,2026-10-05,"+cash.get("id")+",1200,checkpoint\n"));
        assertTrue((Boolean)preview.get("valid"));ledger.commitImport(text(preview,"id"));event("expense","occurred_at","2026-10-06","account_id",cash.get("id"),"amount","100");
        assertEquals("1100",balance(text(cash,"id")));ledger.revertImport(text(preview,"id"));assertEquals("1400",balance(text(cash,"id")));assertTrue((Boolean)ledger.revertImport(text(preview,"id")).get("duplicate"));
        assertEquals(2,ledger.listEvents(50,0,false).get("total"));
    }
    @Test void observationBatchRevertRestoresPriorQuantityAndReplaysTrades() {
        Map<String,Object> cash=account("10000"),position=asset("position","account_id",cash.get("id"),"quantity","10","price","10","as_of","2026-10-01");
        event("buy","occurred_at","2026-10-03","account_id",cash.get("id"),"asset_id",position.get("id"),"quantity","5","price","10");
        Map<String,Object> batch=ledger.previewImport(map("csv_text","type,occurred_at,asset_id,quantity\nposition_observation,2026-10-05,"+position.get("id")+",20\n"));ledger.commitImport(text(batch,"id"));
        event("sell","occurred_at","2026-10-06","account_id",cash.get("id"),"asset_id",position.get("id"),"quantity","2","price","10");
        assertEquals("18",rows(ledger.listAssets(50,0).get("items")).get(0).get("quantity"));ledger.revertImport(text(batch,"id"));assertEquals("13",rows(ledger.listAssets(50,0).get("items")).get(0).get("quantity"));
    }
    @Test void importsAreAtomicIdempotentAndDuplicateBatchDoesNotOwnEarlierTransactions() {
        Map<String,Object> cash=account("0");String csv="type,occurred_at,account_id,amount,external_id\nincome,2026-10-02,"+cash.get("id")+",100,row1\nincome,2026-10-03,"+cash.get("id")+",200,row2\n";
        Map<String,Object> preview=ledger.previewImport(map("csv_text",csv));assertEquals(2,ledger.commitImport(text(preview,"id")).get("inserted"));assertTrue((Boolean)ledger.commitImport(text(preview,"id")).get("duplicate"));
        Map<String,Object> duplicate=ledger.previewImport(map("csv_text",csv));assertEquals(2,obj(duplicate.get("counts")).get("duplicate"));ledger.commitImport(text(duplicate,"id"));ledger.revertImport(text(duplicate,"id"));assertEquals("300",balance(text(cash,"id")));
        Map<String,Object> position=asset("position","account_id",cash.get("id"));Map<String,Object> invalid=ledger.previewImport(map("csv_text","type,occurred_at,account_id,asset_id,amount,quantity,price\nincome,2026-10-04,"+cash.get("id")+",,50,,\nsell,2026-10-05,"+cash.get("id")+","+position.get("id")+",,1,10\n"));
        assertThrows(ResponseStatusException.class,()->ledger.commitImport(text(invalid,"id")));assertEquals("300",balance(text(cash,"id")));assertEquals(2,ledger.listEvents(50,0,false).get("total"));
    }
    @Test void invalidTransferAndConflictCsvStayOutOfLedger() {
        Map<String,Object> cash=account("10000");Map<String,Object> half=ledger.previewImport(map("csv_text","type,occurred_at,account_id,amount\ntransfer,2026-10-02,"+cash.get("id")+",500\n"));
        assertFalse((Boolean)half.get("valid"));assertThrows(ResponseStatusException.class,()->ledger.commitImport(text(half,"id")));
        Map<String,Object> conflict=ledger.previewImport(map("csv_text","type,occurred_at,account_id,amount,external_id\nincome,2026-10-02,"+cash.get("id")+",10,x\nincome,2026-10-02,"+cash.get("id")+",11,x\n"));
        assertEquals(1,obj(conflict.get("counts")).get("conflict"));assertEquals(0,ledger.listEvents(50,0,false).get("total"));
    }
    @Test void csvQuotedNotesAndOpeningDateAreHandled() {
        Map<String,Object> cash=ledger.createAccount(map("name","构造账户","balance","10","as_of","2026-10-03"));
        Map<String,Object> batch=ledger.previewImport(map("csv_text","type,occurred_at,account_id,amount,note\nincome,2026-10-03,"+cash.get("id")+",20,\"第一行,\"\"引号\"\"\n第二行\"\n"));
        assertTrue((Boolean)batch.get("valid"));ledger.commitImport(text(batch,"id"));assertEquals("30",balance(text(cash,"id")));assertEquals("第一行,\"引号\"\n第二行",rows(ledger.listEvents(50,0,false).get("items")).get(0).get("note"));
    }
    @Test void correctionsAndSnapshotsKeepHistoryAndRejectStaleRevision() {
        Map<String,Object> cash=account("0"),original=event("income","account_id",cash.get("id"),"amount","100");long revision=((Number)ledger.summary().get("ledger_revision")).longValue();
        Map<String,Object> first=ledger.saveSnapshot("CNY");assertEquals(first.get("id"),ledger.saveSnapshot("CNY").get("id"));
        event("income","account_id",cash.get("id"),"amount","110","supersedes_id",original.get("id"));assertEquals("110",balance(text(cash,"id")));assertEquals(2,ledger.listEvents(50,0,true).get("total"));
        assertThrows(ResponseStatusException.class,()->event("expense","account_id",cash.get("id"),"amount","10","expected_revision",revision));
        Map<String,Object> second=ledger.saveSnapshot("CNY");assertNotEquals(first.get("id"),second.get("id"));
        Map<String,Object> old=rows(ledger.listSnapshots(50,0).get("items")).stream().filter(item->first.get("id").equals(item.get("id"))).findFirst().get();assertEquals("100.00",obj(old.get("data")).get("net_worth"));
    }
    @Test void revertingCorrectionRestoresOriginalExternalIdDedupIndex() {
        Map<String,Object> cash=account("0");
        Map<String,Object> original=event("income","account_id",cash.get("id"),"amount","100","source","csv-bank","external_id","same-id");
        Map<String,Object> batch=ledger.previewImport(map("source","csv-bank","csv_text","type,occurred_at,account_id,amount,external_id,supersedes_id\nincome,2026-10-10T12:00:00+08:00,"+cash.get("id")+",110,same-id,"+original.get("id")+"\n"));
        assertTrue((Boolean)batch.get("valid"));ledger.commitImport(text(batch,"id"));assertEquals("110",balance(text(cash,"id")));
        ledger.revertImport(text(batch,"id"));assertEquals("100",balance(text(cash,"id")));
        assertTrue((Boolean)event("income","account_id",cash.get("id"),"amount","100","source","csv-bank","external_id","same-id").get("duplicate"));
        assertEquals(1,ledger.listEvents(50,0,false).get("total"));
    }
    @Test void zeroAndNegativeNetWorthStayExactWithoutRatioFabrication() {
        Map<String,Object> cash=account("0"),debt=asset("liability");assertEquals("0.00",ledger.summary().get("net_worth"));
        event("borrow","account_id",cash.get("id"),"liability_id",debt.get("id"),"amount","100");assertEquals("0.00",ledger.summary().get("net_worth"));
        event("expense","occurred_at","2026-10-11","account_id",cash.get("id"),"amount","10");assertEquals("-10.00",ledger.summary().get("net_worth"));assertTrue((Boolean)ledger.summary().get("complete"));
        assertNull(obj(ledger.summary().get("cash_flow")).get("investment_return"));
    }
    @Test void formalWriteRetriesReturnSameEntityEvenAfterRevisionAdvanced() {
        Map<String,Object> request=map("name","构造账户","balance","100","as_of","2026-10-01","idempotency_key","account-request","expected_revision",0);
        Map<String,Object> first=ledger.createAccount(request);assertEquals(first.get("id"),ledger.createAccount(request).get("id"));assertEquals(1,ledger.listAccounts(50,0).get("total"));
        Map<String,Object> positionRequest=map("name","构造持仓","kind","position","account_id",first.get("id"),"idempotency_key","position-request","expected_revision",1);
        Map<String,Object> position=ledger.createAsset(positionRequest);assertEquals(position.get("id"),ledger.createAsset(positionRequest).get("id"));assertEquals(1,ledger.listAssets(50,0).get("total"));
        Map<String,Object> eventRequest=map("type","income","occurred_at","2026-10-10","account_id",first.get("id"),"amount","10","idempotency_key","income-request","expected_revision",2);
        Map<String,Object> firstEvent=ledger.createEvent(eventRequest);assertEquals(firstEvent.get("id"),ledger.createEvent(eventRequest).get("id"));assertEquals("110",balance(text(first,"id")));
        Map<String,Object> conflictRequest=new LinkedHashMap<>(request);conflictRequest.put("name","不同账户");assertThrows(ResponseStatusException.class,()->ledger.createAccount(conflictRequest));
    }
    @Test void restartFromDaoDocumentsAndHistoricalSummaryRebuildExactBalances() throws Exception {
        Map<String,Object> cash=account("0");event("income","occurred_at","2026-10-03","account_id",cash.get("id"),"amount","100");event("expense","occurred_at","2026-10-06","account_id",cash.get("id"),"amount","30");
        FinanceService restarted=new FinanceService(new Store(dao,new ObjectMapper(),manager),()->NOW,new QuoteProvider(url->{throw new IllegalStateException();}));
        assertEquals("70.00",restarted.summary().get("net_worth"));assertEquals("100.00",restarted.summary("CNY","2026-10-04").get("net_worth"));assertEquals("0",obj(restarted.summary("CNY","2026-10-04").get("cash_flow")).get("expense"));
    }
    @Test void failedQuotesKeepPreviousValuesAndCorporateActionRequiresReconciliation() {
        Map<String,Object> cash=account("0"),position=asset("position","account_id",cash.get("id"),"category","etf","symbol","510300","quantity","100","as_of","2026-10-01");
        AtomicReference<String> price=new AtomicReference<>("4.5");AtomicReference<Boolean> fail=new AtomicReference<>(false);
        ledger.setQuoteProvider(new QuoteProvider(url->{if(fail.get())throw new IllegalStateException();return QuoteProviderTest.payload("sh510300",price.get(),"20261013163000");}));
        assertEquals(1,rows(ledger.refreshQuotes().get("updated")).size());assertEquals("450.00",ledger.summary().get("net_worth"));assertTrue((Boolean)ledger.summary().get("fresh"));
        fail.set(true);assertTrue((Boolean)rows(ledger.refreshQuotes().get("failed")).get(0).get("retained_previous"));assertEquals("450.00",ledger.summary().get("net_worth"));assertFalse((Boolean)ledger.summary().get("fresh"));
        fail.set(false);price.set("1.5");assertEquals("needs_reconciliation",rows(ledger.refreshQuotes().get("updated")).get(0).get("status"));
        event("position_observation","occurred_at","2026-10-13T16:45:00+08:00","asset_id",position.get("id"),"quantity","300");assertEquals("valid",rows(ledger.refreshQuotes().get("updated")).get(0).get("status"));
    }
}
