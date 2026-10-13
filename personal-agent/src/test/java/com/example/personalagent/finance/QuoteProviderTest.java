package com.example.personalagent.finance;

import org.junit.jupiter.api.Test;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;

class QuoteProviderTest {
    static String payload(String symbol,String price,String timestamp) {
        String[] fields=new String[53];Arrays.fill(fields,"");fields[1]="构造ETF";fields[2]=symbol.substring(2);fields[3]=price;fields[4]="4.4";fields[30]=timestamp;
        return "v_"+symbol+"=\""+String.join("~",fields)+"\";";
    }
    @Test void endpointEncodingAndEtfMarketAreFixed() {
        QuoteProvider provider=new QuoteProvider(url->{assertEquals("https://qt.gtimg.cn/q=sh510300",url);return payload("sh510300","4.5","20261013163000");});
        Map<String,Object> quote=provider.fetch(Collections.singletonList("510300")).get("sh510300");
        assertEquals("4.5",quote.get("price"));assertEquals("2026-10-13T08:30:00Z",quote.get("market_time"));assertEquals("sz159915",QuoteProvider.normalizeSymbol("159915"));
        for(String invalid:Arrays.asList("http://localhost","sh000001","../../secrets","510300,sh600000","HK00700"))assertThrows(IllegalArgumentException.class,()->QuoteProvider.normalizeSymbol(invalid));
    }
    @Test void invalidPriceMissingFieldsWrongSymbolAndInvalidTimeAreOmitted() {
        for(String price:Arrays.asList("0","NaN","Infinity","-1"))assertTrue(QuoteProvider.parse(payload("sh510300",price,"20261013163000"),Collections.singletonList("sh510300")).isEmpty());
        assertTrue(QuoteProvider.parse(payload("sh510300","4.5","invalid"),Collections.singletonList("sh510300")).isEmpty());
        assertTrue(QuoteProvider.parse(payload("sh510300","4.5","20260230123000"),Collections.singletonList("sh510300")).isEmpty());
        assertTrue(QuoteProvider.parse(payload("sz159915","4.5","20261013163000"),Collections.singletonList("sh510300")).isEmpty());
    }
    @Test void networkErrorDoesNotExposeTransportInformation() {
        QuoteProvider provider=new QuoteProvider(url->{throw new IllegalStateException("构造运输异常信息");});
        IllegalStateException error=assertThrows(IllegalStateException.class,()->provider.fetch(Collections.singletonList("sh510300")));
        assertEquals("行情来源暂时不可用，请稍后重试",error.getMessage());assertNull(error.getCause());
    }
}
