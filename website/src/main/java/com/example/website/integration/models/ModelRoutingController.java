package com.example.website.integration.models;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.springframework.http.*;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;
import javax.servlet.http.*;
import java.net.*;
import java.util.*;
import com.example.website.integration.local.LocalServicesManager;

@RestController
@RequestMapping("/api/models")
public class ModelRoutingController {
    private final ModelRoutingService service;
    private final LocalServicesManager local;
    public ModelRoutingController(ModelRoutingService service,LocalServicesManager local){this.service=service;this.local=local;}
    @GetMapping public Map<String,Object> catalog(HttpServletRequest req,HttpServletResponse res){guard(req,res,false);return service.catalog(false);}
    @PostMapping("/refresh") public Map<String,Object> refresh(HttpServletRequest req,HttpServletResponse res){guard(req,res,true);return service.catalog(true);}
    @PostMapping("/local/strata/start") public Map<String,Object> startLocal(HttpServletRequest req,HttpServletResponse res){guard(req,res,true);local.action("strata","start");return service.catalog(true);}
    @GetMapping("/effective/{scope}") public Map<String,Object> effective(@PathVariable String scope,HttpServletRequest req,HttpServletResponse res){guard(req,res,false);return service.effective(scope);}
    @PutMapping("/selection/{scope}") public Map<String,Object> select(@PathVariable String scope,@RequestBody Map<String,String> body,HttpServletRequest req,HttpServletResponse res){guard(req,res,true);return service.select(scope,body.get("modelId"));}
    @PostMapping("/chat/{scope}") public JsonNode chat(@PathVariable String scope,@RequestBody ObjectNode body,HttpServletRequest req,HttpServletResponse res){guard(req,res,true);if(req.getHeader("Origin")!=null)throw new ResponseStatusException(HttpStatus.FORBIDDEN,"生成接口仅限服务端调用");return service.chat(scope,body);}
    @RequestMapping(value={"","/**"},method=RequestMethod.OPTIONS)
    public ResponseEntity<Void> options(HttpServletRequest req,HttpServletResponse res){guard(req,res,false);res.setHeader("Access-Control-Allow-Methods","GET, PUT, POST, OPTIONS");res.setHeader("Access-Control-Allow-Headers","Content-Type, X-Love530-Model");res.setHeader("Access-Control-Max-Age","600");return ResponseEntity.noContent().build();}
    static void guard(HttpServletRequest req,HttpServletResponse res,boolean write) {
        try {
            if(!InetAddress.getByName(req.getRemoteAddr()).isLoopbackAddress() || !local(req.getServerName())) throw new Exception();
            String origin=req.getHeader("Origin");
            if(origin!=null) {
                URI uri=URI.create(origin);int port=uri.getPort();
                if(!local(uri.getHost()) || !"http".equals(uri.getScheme()) || !(port==req.getServerPort() || Arrays.asList(8080,5174,5176,5177,5178).contains(port))) throw new Exception();
                res.setHeader("Access-Control-Allow-Origin",origin);res.setHeader("Vary","Origin");
            }
            if(write && !"1".equals(req.getHeader("X-Love530-Model"))) throw new Exception();
            res.setHeader("Cache-Control","no-store");
        } catch(Exception e){throw new ResponseStatusException(HttpStatus.FORBIDDEN,"请通过本机服务页面管理模型");}
    }
    private static boolean local(String h){return "localhost".equalsIgnoreCase(h)||"127.0.0.1".equals(h)||"::1".equals(h)||"[::1]".equals(h);}
    @ExceptionHandler(ResponseStatusException.class)
    public ResponseEntity<Map<String,Object>> error(ResponseStatusException e){Map<String,Object> body=new LinkedHashMap<>();body.put("success",false);body.put("message",e.getReason());return ResponseEntity.status(e.getStatus()).body(body);}
}
