package com.example.personalagent.service;

import com.example.personalagent.AgentConfig;
import com.example.personalagent.finance.FinanceService;
import com.example.personalagent.storage.Store;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.stereotype.Service;
import org.springframework.scheduling.annotation.Scheduled;
import java.math.*;
import java.time.*;
import java.util.*;
import static com.example.personalagent.Api.*;

@Service
public class FinanceMonitor {
    private final FinanceService finance;private final Store store;private final AgentService agent;private final RecordService records;private final VaultService vault;private final AgentConfig config;private final ObjectMapper json;
    public FinanceMonitor(FinanceService finance,Store store,AgentService agent,RecordService records,VaultService vault,AgentConfig config,ObjectMapper json){this.finance=finance;this.store=store;this.agent=agent;this.records=records;this.vault=vault;this.config=config;this.json=json;}
    @Scheduled(fixedDelay=5000) public synchronized void tick(){if(!config.isBackground())return;try{check();}catch(Exception ignored){}}
    public synchronized void check()throws Exception {
        Map<String,Object> settings=agent.settings(),state=store.get("finance_monitor","state");if(state==null)state=new LinkedHashMap<>();String last=text(state,"last_quote_at");long minutes=((Number)settings.get("quote_refresh_minutes")).longValue();
        if(last.isEmpty()||Duration.between(Instant.parse(last),Instant.now()).toMinutes()>=minutes){if(!store.list("finance_assets").isEmpty())finance.refreshQuotes();state.put("last_quote_at",now());store.put("finance_monitor","state",state);}
        Map<String,Object> summary=finance.summary(String.valueOf(settings.get("base_currency")),null);store.put("finance_monitor","current",summary);
        String fingerprint=summary.get("ledger_revision")+":"+summary.get("quote_revision")+":"+summary.get("base_currency");
        if(!fingerprint.equals(state.get("published_revision"))){vault.current("50-财富/当前概览.md","# 当前财富概览\n\n截至 "+summary.get("as_of")+"\n\n```json\n"+json.writerWithDefaultPrettyPrinter().writeValueAsString(summary)+"\n```\n");state.put("published_revision",fingerprint);store.put("finance_monitor","state",state);}
        if(!Boolean.TRUE.equals(summary.get("complete"))||!Boolean.TRUE.equals(summary.get("fresh")))return;
        Map<String,Object> baseline=store.get("finance_monitor","baseline");if(baseline==null){store.put("finance_monitor","baseline",summary);return;}
        String previous=text(state,"last_trigger_at");if(!previous.isEmpty()&&Duration.between(Instant.parse(previous),Instant.now()).toHours()<((Number)settings.get("review_cooldown_hours")).longValue())return;
        BigDecimal net=new BigDecimal(text(summary,"net_worth")),old=new BigDecimal(text(baseline,"net_worth")),absolute=new BigDecimal(String.valueOf(settings.get("net_worth_change_amount")));BigDecimal investment=investment(summary),oldInvestment=investment(baseline);boolean significant=net.subtract(old).abs().compareTo(absolute)>=0;
        if(oldInvestment.signum()>0&&investment.signum()>=0){BigDecimal percent=investment.subtract(oldInvestment).abs().multiply(new BigDecimal("100")).divide(oldInvestment,8,RoundingMode.HALF_EVEN);significant|=percent.compareTo(new BigDecimal(String.valueOf(settings.get("investment_change_percent"))))>=0;}
        if(!significant)return;
        Map<String,Object> r=records.create("finance_snapshot",map("title","财富状态出现明显变化","content",json.writerWithDefaultPrettyPrinter().writeValueAsString(map("baseline",baseline,"current",summary)),"important",true,"as_of",summary.get("as_of")),"wealth","active");
        state.put("last_trigger_at",now());store.put("finance_monitor","state",state);store.put("finance_monitor","baseline",summary);vault.current("50-财富/当前概览.md","# 当前财富概览\n\n截至 "+summary.get("as_of")+"\n\n```json\n"+json.writerWithDefaultPrettyPrinter().writeValueAsString(summary)+"\n```\n");vault.flush();
    }
    private BigDecimal investment(Map<String,Object> summary){BigDecimal sum=BigDecimal.ZERO;Object rows=summary.get("assets");if(rows instanceof List)for(Object raw:(List)rows){Map<String,Object> asset=(Map<String,Object>)raw;if("position".equals(asset.get("kind"))&&asset.get("base_value")!=null)sum=sum.add(new BigDecimal(String.valueOf(asset.get("base_value"))));}return sum;}
}
