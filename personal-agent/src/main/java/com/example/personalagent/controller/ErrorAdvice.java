package com.example.personalagent.controller;
import com.example.personalagent.Api;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.http.*;
import java.util.*;
@RestControllerAdvice
public class ErrorAdvice {
    @ExceptionHandler(ResponseStatusException.class) public ResponseEntity<?> expected(ResponseStatusException e){return ResponseEntity.status(e.getStatus()).body(Api.map("success",false,"message",e.getReason()));}
    @ExceptionHandler({IllegalArgumentException.class,org.springframework.http.converter.HttpMessageNotReadableException.class}) public ResponseEntity<?> invalid(Exception e){return ResponseEntity.badRequest().body(Api.map("success",false,"message","输入格式无效，请检查字段"));}
    @ExceptionHandler(Exception.class) public ResponseEntity<?> unexpected(Exception e){return ResponseEntity.status(500).body(Api.map("success",false,"message","操作未完成，请检查本地数据目录与服务状态"));}
}
