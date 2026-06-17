# AGENTS.md

## 椤圭洰姒傝堪

`website` 鏄?`love530` Maven 鑱氬悎宸ョ▼涓殑涓汉涓婚〉/灞曠ず绔欑偣 Web 寰湇鍔★紝璺緞锛?

```text
C:/Code/Java_Code/love5000/website
```

鏍稿績鍔熻兘锛?

- 鎻愪緵涓汉涓婚〉闈欐€佺珯鐐广€?
- 缁熶竴鎵胯浇 `python-a`銆乣quant-a`銆乣video` 涓変釜鐙珛 Python 瀛愭湇鍔＄殑浠ｇ爜鐩綍銆侀椤靛叆鍙ｃ€佸仴搴锋娴嬪拰鑷姩鍚姩閰嶇疆銆?
- 鎻愪緵鎻愮ず璇嶆帶鍒跺彴鍜岄潤鎬佹彁绀鸿瘝搴撻〉闈€?
- 鎻愪緵鍩虹 Spring MVC Web Demo銆?
- 淇濈暀 OSS Demo 鍜?Nacos Discovery 绀轰緥浠ｇ爜銆?
- 浣跨敤 MySQL 鍜?Druid 浣滀负鍚庣鏁版嵁婧愰厤缃€?

鎶€鏈爤锛?

- Java 8
- Maven
- Spring Boot 2.6.13
- Spring MVC
- MyBatis / DAO 鎺ュ彛 + XML Mapper 鏄犲皠鍣?
- MySQL Connector/J
- Alibaba Druid 1.1.22
- JUnit 5 / Spring Boot Test
- HTML / CSS / JavaScript

閰嶇疆鏂囦欢锛?

- `pom.xml`锛氭ā鍧椾緷璧栥€丣ava 8 缂栬瘧閰嶇疆銆丼pring Boot 涓荤被銆?
- `src/main/resources/application.properties`锛氱鍙ｅ拰鍘嗗彶绀轰緥閰嶇疆銆?
- `src/main/resources/application.yml`锛歁ySQL銆丏ruid銆侀潤鎬佽祫婧愯矾寰勶紝浠ュ強涓変釜 Python 瀛愭湇鍔＄殑鑷姩鍚姩閰嶇疆銆?

**鍏抽敭**锛歚website` 鏄彲鐙珛鍚姩鐨?Web 鏈嶅姟锛岄粯璁ょ鍙ｄ负 `8080`銆?

**鍏抽敭**锛歚python-a`銆乣quant-a`銆乣video` 鏀惧湪 `website/` 鐩綍涓嬶紝浣嗕粛鐒舵槸鐙珛 Python 鏈嶅姟锛屼笉鏄?Java Maven 妯″潡锛屼笉鍔犲叆鐖?`pom.xml` 鐨?`<modules>`銆?

**鍏抽敭**锛氱洿鎺ュ惎鍔?`website` 鏃朵細鑷姩妫€鏌ュ苟鎷夎捣 `website/python-a`銆乣website/quant-a`銆乣website/video`銆傞粯璁や細鎶婁笁涓?Python 瀛愭湇鍔＄殑 stdout/stderr 缁ф壙鍒?`website` 鎺у埗鍙帮紝渚夸簬鍦?IDEA Run/Terminal 涓煡鐪嬭繍琛屾棩蹇楀拰鎺ュ彛璁块棶鏃ュ織銆?

**鏂囨。鍚屾绾﹀畾**锛氭瘡娆′慨鏀?`website` 鐨勯椤靛叆鍙ｃ€佹彁绀鸿瘝鎺у埗鍙般€佸崥瀹€佽嚜鍔ㄥ惎鍔ㄩ厤缃€丳ython 瀛愭湇鍔￠泦鎴愩€佺鍙ｃ€丄PI銆侀潤鎬佽祫婧愮洰褰曟垨娴嬭瘯鏂瑰紡鏃讹紝蹇呴』鍚屾鏇存柊鏈枃浠躲€乣website/README.md`锛屼互鍙婃牴鐩綍 `AGENTS.md` / `README.md` 涓浉鍏冲唴瀹广€?

## 寮€鍙戝懡浠?

榛樿浠庝粨搴撴牴鐩綍鎵ц锛?

```bash
cd C:/Code/Java_Code/love5000
```

瀹夎渚濊禆骞剁紪璇戝綋鍓嶆湇鍔★細

```bash
mvn -pl website -am clean install
```

鍚姩鏈嶅姟锛?

```bash
mvn -pl website -am spring-boot:run
```

鏈嶅姟鍦板潃锛?

```text
http://localhost:8080/
```

杩愯褰撳墠鏈嶅姟娴嬭瘯锛?

```bash
mvn -pl website -am test
```

鎵撳寘褰撳墠鏈嶅姟锛?

```bash
mvn -pl website -am clean package
```

璺宠繃娴嬭瘯鎵撳寘锛?

```bash
mvn -pl website -am clean package -DskipTests
```

妫€鏌ヤ緷璧栨爲锛?

```bash
mvn -pl website dependency:tree
```

浠庢ā鍧楃洰褰曞惎鍔細

```bash
cd C:/Code/Java_Code/love5000/website
mvn spring-boot:run
```

鍗曠嫭鍚姩 `python-a`锛?

```bash
cd C:/Code/Java_Code/love5000/website/python-a
python server.py
```

鍗曠嫭鍚姩 `quant-a`锛?

```bash
cd C:/Code/Java_Code/love5000/website/quant-a
python -m uvicorn main:app --host 127.0.0.1 --port 5175
```

鍗曠嫭鍚姩 `video`锛?

```bash
cd C:/Code/Java_Code/love5000/website/video
python web_server.py --host 127.0.0.1 --port 5176
```

## 椤圭洰缁撴瀯

```text
website/
鈹溾攢鈹€ pom.xml
鈹溾攢鈹€ AGENTS.md
鈹溾攢鈹€ python-a/
鈹?  鈹溾攢鈹€ server.py
鈹?  鈹溾攢鈹€ index.html
鈹?  鈹溾攢鈹€ app.js
鈹?  鈹斺攢鈹€ obsidian-vault/
鈹溾攢鈹€ quant-a/
鈹?  鈹溾攢鈹€ main.py
鈹?  鈹溾攢鈹€ quant/
鈹?  鈹溾攢鈹€ tests/
鈹?  鈹斺攢鈹€ web/
鈹溾攢鈹€ video/
鈹?  鈹溾攢鈹€ web_server.py
鈹?  鈹溾攢鈹€ anime_tools/
鈹?  鈹溾攢鈹€ tests/
鈹?  鈹斺攢鈹€ web/
鈹斺攢鈹€ src/
    鈹溾攢鈹€ main/
    鈹?  鈹溾攢鈹€ java/com/example/website/
    鈹?  鈹?  鈹溾攢鈹€ WebsiteApplication.java
    鈹?  鈹?  鈹溾攢鈹€ auth/
    鈹?  鈹?  鈹?  鈹溾攢鈹€ WebsiteAuthUserRepository.java
    鈹?  鈹?  鈹?  鈹斺攢鈹€ dao/WebsiteAuthUserDao.java
    鈹?  鈹?  鈹溾攢鈹€ blog/
    鈹?  鈹?  鈹?  鈹溾攢鈹€ controller/
    鈹?  鈹?  鈹?  鈹溾攢鈹€ dao/
    鈹?  鈹?  鈹?  鈹溾攢鈹€ dto/
    鈹?  鈹?  鈹?  鈹溾攢鈹€ model/
    鈹?  鈹?  鈹?  鈹斺攢鈹€ service/
    鈹?  鈹?  鈹溾攢鈹€ demos/
    鈹?  鈹?  鈹?  鈹溾攢鈹€ nacosdiscoveryconsumer/
    鈹?  鈹?  鈹?  鈹溾攢鈹€ nacosdiscoveryprovider/
    鈹?  鈹?  鈹?  鈹溾攢鈹€ oss/
    鈹?  鈹?  鈹?  鈹斺攢鈹€ web/
    鈹?  鈹?  鈹溾攢鈹€ nacosdiscovery/
    鈹?  鈹?  鈹斺攢鈹€ prompt/
    鈹?  鈹斺攢鈹€ resources/
    鈹?      鈹溾攢鈹€ application.properties
    鈹?      鈹溾攢鈹€ application.yml
    鈹?      鈹溾攢鈹€ index.html
    鈹?      鈹溾攢鈹€ mapper/
    鈹?      鈹?  鈹溾攢鈹€ auth/WebsiteAuthUserMapper.xml
    鈹?      鈹?  鈹斺攢鈹€ blog/BlogArticleMapper.xml
    鈹?      鈹溾攢鈹€ README.md
    鈹?      鈹斺攢鈹€ static/
    鈹?          鈹溾攢鈹€ css/style.css
    鈹?          鈹溾攢鈹€ js/script.js
    鈹?          鈹溾攢鈹€ img/
    鈹?          鈹溾攢鈹€ media/
    鈹?          鈹溾攢鈹€ prompt-console/
    鈹?          鈹溾攢鈹€ soundeffects/
    鈹?          鈹斺攢鈹€ svg/
    鈹斺攢鈹€ test/java/com/example/website/
        鈹斺攢鈹€ WebsiteApplicationTests.java
```

鏍稿績妯″潡鑱岃矗锛?

- `WebsiteApplication.java`锛歋pring Boot 鍚姩绫汇€?
- `integration/PythonAAutoStartRunner.java`锛氬惎鍔ㄦ垨澶嶇敤 `website/python-a`锛屽仴搴锋鏌ュ湴鍧€涓?`http://127.0.0.1:5174/api/health`銆?
- `integration/QuantAAutoStartRunner.java`锛氬惎鍔ㄦ垨澶嶇敤 `website/quant-a`锛屽仴搴锋鏌ュ湴鍧€涓?`http://127.0.0.1:5175/api/health`銆?
- `integration/VideoAutoStartRunner.java`锛氬惎鍔ㄦ垨澶嶇敤 `website/video`锛屽仴搴锋鏌ュ湴鍧€涓?`http://127.0.0.1:5176/api/health`銆?
- `auth/WebsiteAuthUserRepository.java`锛氶€傞厤 `common` 鐨?`AuthUserRepository`锛屼笉鐩存帴鍐?SQL銆?
- `auth/dao/WebsiteAuthUserDao.java`锛氳璇佺敤鎴疯〃 MyBatis DAO銆?
- `blog/controller`锛氬崥瀹?REST API銆?
- `blog/service`锛氬崥瀹笟鍔¤鍒欍€?
- `blog/dao`锛氬崥瀹㈡枃绔?MyBatis DAO銆?
- `mapper/auth`銆乣mapper/blog`锛歁yBatis XML Mapper锛岄泦涓淮鎶ゆ暟鎹簱 CRUD SQL銆?
- `demos/web`锛氬熀纭€ Web Controller 绀轰緥銆?
- `demos/oss`锛歄SS 绀轰緥浠ｇ爜銆?
- `demos/nacosdiscoveryconsumer`锛歂acos 娑堣垂鑰呯ず渚嬨€?
- `demos/nacosdiscoveryprovider`锛歂acos 鎻愪緵鑰呯ず渚嬨€?
- `nacosdiscovery`锛歂acos Discovery 閰嶇疆銆?
- `prompt/controller/PromptConsoleController.java`锛氭彁绀鸿瘝鎺у埗鍙?API銆?- `prompt/service`锛氭彁绀鸿瘝鏉ユ簮鎷夊彇銆佹憳瑕併€佺粍鍚堝拰娉ㄥ唽鏈嶅姟銆?- `static/prompt-console`锛氭彁绀鸿瘝鎺у埗鍙板墠绔拰闈欐€佹彁绀鸿瘝搴撴暟鎹€?- `static/prompt-console/prompt-category-groups.js`锛氶潤鎬佹彁绀鸿瘝搴撯€滃ぇ鍒嗙被 -> 灏忓垎绫烩€濇槧灏勫拰缁熻閫昏緫銆傛柊澧炲皬绫绘椂浼樺厛琛ュ厖璇ユ槧灏勶紱鏈槧灏勫皬绫昏嚜鍔ㄥ綊鍏モ€滃叾浠栤€濄€?- `static/css/style.css`锛氱珯鐐规牱寮忋€?
- `static/js/script.js`锛氱珯鐐逛氦浜掑拰棣栭〉鏈嶅姟鍗＄墖鍋ュ悍妫€娴嬨€?
- `static/img`銆乣static/svg`銆乣static/soundeffects`锛氬浘鐗囥€佸浘鏍囥€侀煶鏁堣祫婧愩€?
- `python-a/`锛欰 鑲¤嚜閫夎偂 AI 鐮旂┒鍙帮紝鐙珛 ThreadingHTTPServer 鏈嶅姟锛岄粯璁ょ鍙?`5174`銆?
- `quant-a/`锛欰 鑲￠噺鍖栫爺绌跺彴锛岀嫭绔?FastAPI 鏈嶅姟锛岄粯璁ょ鍙?`5175`銆?
- `video/`锛欰I 瑙嗛宸ヤ綔鍙帮紝鐙珛 Python Web 鏈嶅姟锛岄粯璁ょ鍙?`5176`銆?

## 閰嶇疆绾﹀畾

榛樿绔彛锛?

```properties
server.port=8080
```

瀛愭湇鍔＄鍙ｏ細

```text
python-a: 5174
quant-a: 5175
video: 5176
```

闈欐€佽祫婧愯矾寰勶細

```yaml
spring:
  web:
    resources:
      static-locations:
        - classpath:/static/
```

鏁版嵁搴撻厤缃細

```yaml
spring:
  datasource:
    type: com.alibaba.druid.pool.DruidDataSource
    driver-class-name: com.mysql.cj.jdbc.Driver
```

鈿狅笍 涓ラ噸璀﹀憡锛氫笉瑕佹彁浜ょ湡瀹炴暟鎹簱瀵嗙爜銆傛柊澧為厤缃椂浣跨敤鐜鍙橀噺锛屼緥濡?`${WEBSITE_DB_PASSWORD}`銆?

鏁版嵁搴撹闂害瀹氾細

- 鎵€鏈夋暟鎹簱 CRUD 閮戒娇鐢?MyBatis DAO 鎺ュ彛 + XML Mapper 鏄犲皠鍣ㄣ€?
- DAO 鎺ュ彛鏀惧湪瀵瑰簲涓氬姟鍖呯殑 `dao` 瀛愬寘涓紝绫诲悕浠?`Dao` 缁撳熬銆?
- Mapper XML 鏀惧湪 `src/main/resources/mapper` 涓嬶紝鏂囦欢鍚嶄互 `Mapper.xml` 缁撳熬銆?
- 蹇呴』鍦?`application.yml` 鏄惧紡閰嶇疆 XML Mapper 鎵弿璺緞锛?

```yaml
mybatis:
  mapper-locations: classpath*:mapper/**/*.xml
  type-aliases-package: com.example.website.blog.model,com.example.common.auth.model
  configuration:
    map-underscore-to-camel-case: true
```

- SQL 涓嶅啓鍦?Controller銆丼ervice 鎴栨櫘閫?Java 绫婚噷銆?
- 涓嶅啀鏂板 `JdbcTemplate`銆乣PreparedStatement`銆丣PA Repository 鎴?Java 鍐呰仈 SQL銆?
- 鏁版嵁搴撹〃鐢卞紑鍙戣€呮垨杩愮淮鎻愬墠鍒涘缓锛孞ava 鍚姩娴佺▼涓嶈礋璐ｅ缓琛ㄣ€佽ˉ瀛楁鎴栧啓绉嶅瓙鏁版嵁銆?

Python 瀛愭湇鍔¤嚜鍔ㄥ惎鍔ㄧ害瀹氾細

```yaml
python-a:
  auto-start:
    work-dir: website/python-a
    log-to-console: true

quant-a:
  auto-start:
    work-dir: website/quant-a
    log-to-console: true

video:
  auto-start:
    work-dir: website/video
    log-to-console: true
```

- `log-to-console: true` 鏃讹紝瀛愭湇鍔℃棩蹇椾細鐩存帴杩涘叆 `website` 鐨勬帶鍒跺彴銆?
- `log-to-console: false` 鏃讹紝鏃ュ織鍐欏叆瀵瑰簲瀛愭湇鍔＄洰褰曚笅鐨?`server.out.log` 鍜?`server.err.log`銆?
- 鍗曞厓娴嬭瘯蹇呴』鍏抽棴涓変釜鑷姩鍚姩寮€鍏筹紝閬垮厤娴嬭瘯鍚姩澶栭儴 Python 杩涚▼銆?

## 浠ｇ爜瑙勮寖

Java 鍛藉悕锛?

- 绫诲悕浣跨敤 `UpperCamelCase`锛歚WebsiteApplication`銆乣BasicController`銆?
- 鏂规硶鍚嶅拰鍙橀噺鍚嶄娇鐢?`lowerCamelCase`銆?
- 甯搁噺浣跨敤 `UPPER_SNAKE_CASE`銆?
- 鍖呭悕鍏ㄥ皬鍐欙細`com.example.website`銆?
- Controller 绫讳互 `Controller` 缁撳熬銆?
- DAO 鎺ュ彛浠?`Dao` 缁撳熬銆?
- Configuration 绫讳互 `Configuration` 鎴?`Config` 缁撳熬銆?

Spring 绾﹀畾锛?

- Controller 鍙斁 HTTP 绀轰緥鎴栭〉闈㈡帴鍙ｏ紝涓嶆壙杞藉鏉備笟鍔￠€昏緫銆?
- 绀轰緥浠ｇ爜鏀惧湪 `demos` 鍖呬笅锛岀敓浜у寲浠ｇ爜涓嶈缁х画濉炶繘 `demos`銆?
- 涓氬姟鏁版嵁搴撹闂斁鍦?DAO + Mapper XML 涓紝Service 鍙鐞嗕笟鍔¤鍒欏拰浜嬪姟杈圭晫銆?
- Nacos 鐩稿叧浠ｇ爜闆嗕腑鍦?`nacosdiscovery` 鍜?`demos/nacosdiscovery*`銆?
- 鏂板閰嶇疆浼樺厛鍐欏叆 `application.yml`锛岀鍙ｇ瓑绠€鍗曞紑鍏冲彲淇濈暀鍦?`application.properties`銆?

鍓嶇闈欐€佽祫婧愮害瀹氾細

- CSS 淇敼鏀惧湪 `src/main/resources/static/css/style.css`銆?
- JS 淇敼鏀惧湪 `src/main/resources/static/js/script.js`銆?
- 鍥剧墖鏀惧湪 `src/main/resources/static/img`銆?
- 濯掍綋鏂囦欢鏀惧湪 `src/main/resources/static/media`銆?
- 鎻愮ず璇嶆帶鍒跺彴鏀惧湪 `src/main/resources/static/prompt-console`銆?
- SVG 鍥炬爣鏀惧湪 `src/main/resources/static/svg`銆?
- 闊虫晥鏀惧湪 `src/main/resources/static/soundeffects`銆?
- 椤甸潰寮曠敤璧勬簮鏃朵娇鐢ㄧ浉瀵硅矾寰勶紝涓嶄娇鐢ㄦ湰鏈虹粷瀵硅矾寰勩€?

## 娴嬭瘯绛栫暐

娴嬭瘯妗嗘灦锛?

- JUnit 5
- Spring Boot Test

杩愯娴嬭瘯锛?

```bash
mvn -pl website -am test
```

鎻愮ず璇嶅簱鍒嗙被鏄犲皠淇敼鍚庤繍琛岋細

```bash
node website/src/test/js/prompt-console/prompt-category-groups.test.js
```

褰撳墠宸叉湁娴嬭瘯锛?
```text
src/test/java/com/example/website/WebsiteApplicationTests.java
```

娴嬭瘯瑕佹眰锛?

- 鏂板 Controller 鏃惰ˉ鍏?Spring MVC 鎴?context 娴嬭瘯銆?
- 鏂板 DAO/Mapper SQL 鏃惰鐩栨垚鍔熻矾寰勩€佺┖缁撴灉鍜屼富瑕佸け璐ヨ矾寰勩€?
- 淇敼 Nacos 绀轰緥鏃讹紝娴嬭瘯涓笉瑕佷緷璧栫湡瀹?Nacos 鏈嶅姟銆?
- 淇敼鏁版嵁搴撶浉鍏抽厤缃椂锛屾祴璇曚腑涓嶈杩炴帴杩滅▼ MySQL銆?
- 淇敼闈欐€侀〉闈㈠悗锛屽惎鍔ㄦ湇鍔″苟璁块棶 `http://localhost:8080/` 鎵嬪姩楠岃瘉銆?
- 淇敼涓変釜 Python 瀛愭湇鍔¤嚜鍔ㄥ惎鍔ㄩ€昏緫鏃讹紝鑷冲皯杩愯瀵瑰簲 `*AutoStartRunnerTest`锛屽苟纭宸ヤ綔鐩綍瑙ｆ瀽浠嶆敮鎸佷粠浠撳簱鏍圭洰褰曞拰 `website/` 妯″潡鐩綍鍚姩銆?

瑕嗙洊鐜囩洰鏍囷細

- Controller 鏂板鍒嗘敮涓嶄綆浜?70%銆?
- 閰嶇疆绫昏嚦灏戣鐩?Spring context 鑳芥甯稿惎鍔ㄣ€?
- 绾潤鎬佽祫婧愭敼鍔ㄤ笉寮哄埗瑕嗙洊鐜囷紝浣嗗繀椤绘墜鍔ㄩ獙璇侀〉闈㈠彲璁块棶銆?

## 鎻愪氦鍓嶆鏌?

```bash
mvn -pl website -am clean test
```

闇€瑕佹墜鍔ㄥ惎鍔ㄩ獙璇佹椂鎵ц锛?

```bash
mvn -pl website -am spring-boot:run
```

妫€鏌ユ竻鍗曪細

- **鍏抽敭**锛氫慨鏀归椤靛叆鍙ｃ€佹彁绀鸿瘝鎺у埗鍙般€佸崥瀹€佽嚜鍔ㄥ惎鍔ㄩ厤缃€丳ython 瀛愭湇鍔￠泦鎴愩€佺鍙ｃ€丄PI銆侀潤鎬佽祫婧愮洰褰曟垨娴嬭瘯鏂瑰紡鏃讹紝鍚屾鏇存柊 `website/AGENTS.md`銆乣website/README.md` 鍜屾牴鏂囨。銆?
- **鍏抽敭**锛氫笉瑕佹妸姝ｅ紡涓氬姟浠ｇ爜缁х画鏀捐繘 `demos` 鍖呫€?
- **鍏抽敭**锛氭柊澧炴垨淇敼鏁版嵁搴?CRUD 鏃跺悓姝ユ洿鏂?DAO銆丮apper XML銆佹ā鍨嬪拰娴嬭瘯銆?
- **鍏抽敭**锛氶潤鎬佽祫婧愯矾寰勫繀椤昏兘浠?`classpath:/static/` 鍔犺浇銆?
- **鍏抽敭**锛氫笁涓?Python 瀛愭湇鍔″繀椤讳繚鐣欏湪 `website/python-a`銆乣website/quant-a`銆乣website/video` 涓嬶紝浣嗕笉瑕佸姞鍏?Maven modules銆?
- **鍏抽敭**锛氭暟鎹簱瀵嗙爜鍜?Nacos 瀵嗙爜浣跨敤鐜鍙橀噺銆?
- 鈿狅笍 涓嶈鍦ㄥ崟鍏冩祴璇曚腑杩炴帴鐪熷疄 Nacos銆佺湡瀹?MySQL 鎴栧閮?OSS銆?
- 鈿狅笍 涓嶈鎻愪氦 `target/`銆両DE 缂撳瓨銆丳ython `__pycache__/`銆乣.pytest_cache/`銆佹湰鍦板瘑閽ャ€佹湇鍔℃棩蹇楁垨瑙嗛鐢熸垚浜х墿銆?

