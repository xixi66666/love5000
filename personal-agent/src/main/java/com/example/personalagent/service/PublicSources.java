package com.example.personalagent.service;

import org.springframework.stereotype.Service;
import java.net.*;
import java.io.*;
import java.util.*;
import javax.xml.parsers.DocumentBuilderFactory;
import org.w3c.dom.*;
import static com.example.personalagent.Api.*;

/** Fixed public feeds: no user question, personal fact or holding is transmitted in a search URL. */
@Service
public class PublicSources {
    private List<Map<String,Object>> cached=new ArrayList<>();private long expires;
    public synchronized List<Map<String,Object>> fetch(){if(System.currentTimeMillis()<expires)return new ArrayList<>(cached);List<Map<String,Object>> items=new ArrayList<>();for(String url:Arrays.asList("https://openai.com/news/rss.xml","https://www.federalreserve.gov/feeds/press_all.xml"))try{items.addAll(read(url));}catch(Exception ignored){}cached=items;expires=System.currentTimeMillis()+1800000;return new ArrayList<>(items);}
    private List<Map<String,Object>> read(String url)throws Exception{HttpURLConnection conn=(HttpURLConnection)new URL(url).openConnection();conn.setInstanceFollowRedirects(false);conn.setConnectTimeout(5000);conn.setReadTimeout(5000);conn.setRequestProperty("User-Agent","Love530PersonalAgent/0.1");try{if(conn.getResponseCode()!=200)return Collections.emptyList();ByteArrayOutputStream bytes=new ByteArrayOutputStream();try(InputStream input=conn.getInputStream()){byte[] buffer=new byte[8192];int n;while((n=input.read(buffer))>=0){if(bytes.size()+n>2000000)throw new IOException("公开信息过大");bytes.write(buffer,0,n);}}
        DocumentBuilderFactory factory=DocumentBuilderFactory.newInstance();factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl",true);factory.setFeature("http://xml.org/sax/features/external-general-entities",false);factory.setFeature("http://xml.org/sax/features/external-parameter-entities",false);factory.setXIncludeAware(false);factory.setExpandEntityReferences(false);Document doc=factory.newDocumentBuilder().parse(new ByteArrayInputStream(bytes.toByteArray()));NodeList nodes=doc.getElementsByTagName("item");List<Map<String,Object>> result=new ArrayList<>();for(int i=0;i<Math.min(nodes.getLength(),4);i++){Element item=(Element)nodes.item(i);String link=field(item,"link");URI target=URI.create(link);if(!"https".equals(target.getScheme())||target.getHost()==null)continue;result.add(map("source_id","public:"+link,"title",field(item,"title"),"url",link,"text",field(item,"description").replaceAll("<[^>]*>"," ").substring(0,Math.min(1200,field(item,"description").replaceAll("<[^>]*>"," ").length())),"published_at",field(item,"pubDate"),"as_of",now(),"kind","public-feed"));}return result;
    }finally{conn.disconnect();}}
    private String field(Element element,String name){NodeList children=element.getElementsByTagName(name);return children.getLength()==0?"":children.item(0).getTextContent();}
}
