package com.example.personalagent.finance;

import org.springframework.web.bind.annotation.*;
import java.util.*;
import static com.example.personalagent.Api.*;

@RestController
@RequestMapping("/api/finance")
public class FinanceController {
    private final FinanceService service;
    public FinanceController(FinanceService service) { this.service = service; }
    @GetMapping("/accounts") public Map<String,Object> accounts(@RequestParam(defaultValue="50") int limit,@RequestParam(defaultValue="0") int offset) { return ok(service.listAccounts(limit,offset)); }
    @PostMapping("/accounts") public Map<String,Object> account(@RequestBody Map<String,Object> input) { return ok(service.createAccount(input)); }
    @GetMapping("/assets") public Map<String,Object> assets(@RequestParam(defaultValue="50") int limit,@RequestParam(defaultValue="0") int offset) { return ok(service.listAssets(limit,offset)); }
    @PostMapping("/assets") public Map<String,Object> asset(@RequestBody Map<String,Object> input) { return ok(service.createAsset(input)); }
    @GetMapping("/events") public Map<String,Object> events(@RequestParam(defaultValue="50") int limit,@RequestParam(defaultValue="0") int offset,@RequestParam(defaultValue="false") boolean include_inactive) { return ok(service.listEvents(limit,offset,include_inactive)); }
    @PostMapping("/events") public Map<String,Object> event(@RequestBody Map<String,Object> input) { return ok(service.createEvent(input)); }
    @GetMapping("/imports") public Map<String,Object> imports(@RequestParam(defaultValue="50") int limit,@RequestParam(defaultValue="0") int offset) { return ok(service.listImports(limit,offset)); }
    @PostMapping("/imports/preview") public Map<String,Object> preview(@RequestBody Map<String,Object> input) { return ok(service.previewImport(input)); }
    @PostMapping("/imports/{id}/commit") public Map<String,Object> commit(@PathVariable String id) { return ok(service.commitImport(id)); }
    @PostMapping("/imports/{id}/revert") public Map<String,Object> revert(@PathVariable String id) { return ok(service.revertImport(id)); }
    @GetMapping("/summary") public Map<String,Object> summary(@RequestParam(defaultValue="CNY") String base_currency,@RequestParam(required=false) String as_of) { return ok(service.summary(base_currency,as_of)); }
    @GetMapping("/snapshots") public Map<String,Object> snapshots(@RequestParam(defaultValue="50") int limit,@RequestParam(defaultValue="0") int offset) { return ok(service.listSnapshots(limit,offset)); }
    @PostMapping("/snapshots") public Map<String,Object> snapshot(@RequestBody(required=false) Map<String,Object> input) { return ok(service.saveSnapshot(input==null ? "CNY" : String.valueOf(input.getOrDefault("base_currency","CNY")))); }
    @PostMapping("/quotes/refresh") public Map<String,Object> refresh(@RequestBody(required=false) Map<String,Object> input) { require(input==null || input.isEmpty(),"行情刷新不接受自定义 URL 或其他参数");return ok(service.refreshQuotes()); }
    @PostMapping("/rates") public Map<String,Object> rate(@RequestBody Map<String,Object> input) { return ok(service.setRate(input)); }
}
