# love5000 / love530

`love5000` 鏄竴涓?Java 8 + Spring Boot 2.6.13 鐨?Maven 澶氭ā鍧楅」鐩紝鐖跺伐绋?artifactId 涓?`love530`銆備粨搴撳悓鏃舵墭绠′笁涓嫭绔?Python 寰簲鐢紝鐢ㄤ簬 A 鑲＄爺绌躲€侀噺鍖栫爺绌跺拰 AI 鍔ㄦ极鐭墖鐢熸垚銆?

## 妯″潡

Maven 鑱氬悎妯″潡锛?

- `common`锛氬叕鍏?OSS 宸ュ叿銆佽嚜鍔ㄩ厤缃拰閫氱敤 Session 璁よ瘉鑳藉姏銆?
- `lovestory`锛氭亱鐖辩浉鍐屻€佺収鐗囦笂浼犮€佺暀瑷€鏉垮拰鍚変粬瑙嗛鍗＄墖 Web 搴旂敤銆?
- `website`锛氫釜浜轰富椤?灞曠ず绔欑偣銆佸崥瀹€佹彁绀鸿瘝鎺у埗鍙帮紝浠ュ強 Python 瀛愭湇鍔″叆鍙ｅ拰鑷姩鍚姩銆?- `imagetemplate`锛氬浘鐗囨彁绀鸿瘝妯℃澘搴撳拰 OpenAI Images API 鐢熸垚鏈嶅姟銆?
`website` 鐨勯潤鎬佹彁绀鸿瘝搴撲綅浜?`website/src/main/resources/static/prompt-console/`銆傚垎绫婚噰鐢ㄢ€滃ぇ鍒嗙被 -> 灏忓垎绫烩€濅袱绾х粨鏋勶紝鏄犲皠缁存姢鍦?`prompt-category-groups.js`锛屽垎绫婚€昏緫鍙敤浠ヤ笅鍛戒护鍗曠嫭楠岃瘉锛?
```bash
node website/src/test/js/prompt-console/prompt-category-groups.test.js
```

鐙珛 Python 寰簲鐢細

- `website/python-a`锛欰 鑲¤嚜閫夎偂 AI 鐮旂┒鍙帮紝榛樿绔彛 `5174`銆?
- `website/quant-a`锛欰 鑲″鍥犲瓙閲忓寲鐮旂┒鍙帮紝榛樿绔彛 `5175`銆?
- `website/video`锛欰I 鍘熷垱鍔ㄦ极鐭墖鐢熸垚宸ヤ綔鍙帮紝榛樿绔彛 `5176`銆?

鏍圭洰褰曚笅鐨?`python-a/`銆乣quant-a/` 涓嶆槸褰撳墠涓昏鎺ュ叆璺緞锛涘綋鍓嶈繍琛屽拰鏂囨。缁存姢浠?`website/` 涓嬬殑涓変釜瀛愭湇鍔′负鍑嗐€?

## 蹇€熷紑濮?

浠庝粨搴撴牴鐩綍鎵ц锛?

```bash
cd C:/Code/Java_Code/love5000
mvn test
```

鍚姩 `website`锛?

```bash
mvn -pl website -am spring-boot:run
```

`website` 榛樿绔彛涓?`8080`锛屽惎鍔ㄦ椂浼氭鏌ュ苟鑷姩鎷夎捣 `website/python-a`銆乣website/quant-a` 鍜?`website/video`銆傚鏋滃搴斿仴搴锋鏌ュ凡缁忓彲鐢紝浼氬鐢ㄥ凡鏈夋湇鍔°€?

鍏朵粬鏈嶅姟锛?

```bash
mvn -pl lovestory -am spring-boot:run -Dspring-boot.run.main-class=com.ycxandwuqian.love.LovestoryApplication
mvn -pl imagetemplate -am spring-boot:run
```

Python 瀛愭湇鍔″彲鍗曠嫭鍚姩锛?

```bash
cd website/python-a && python server.py
cd website/quant-a && python -m uvicorn main:app --host 127.0.0.1 --port 5175
cd website/video && python web_server.py
```

## 绔彛

- `website`锛歚8080`
- `lovestory`锛歚8081`
- `imagetemplate`锛歚8082`
- `python-a`锛歚5174`
- `quant-a`锛歚5175`
- `video`锛歚5176`

## 娴嬭瘯

Java 妯″潡锛?

```bash
mvn test
mvn -pl common test
mvn -pl lovestory -am test
mvn -pl website -am test
mvn -pl imagetemplate -am test
```

Python 瀛愭湇鍔★細

```bash
cd website/python-a && python -m unittest discover -s tests -v
cd website/quant-a && python -m pytest -v
cd website/video && python -m unittest discover -s tests -v
```

## 閰嶇疆涓庡畨鍏?

涓嶈鎻愪氦鐪熷疄鏁版嵁搴撳瘑鐮併€丱SS AccessKey銆丱penAI API Key銆丏eepSeek Key銆乀ushare Token銆佽吘璁簯瀵嗛挜鎴?DashScope Key銆傛柊澧為厤缃紭鍏堜娇鐢ㄧ幆澧冨彉閲忔垨鏈湴绉佹湁閰嶇疆鏂囦欢銆?

甯歌绉佹湁鏂囦欢宸插湪 `.gitignore` 涓拷鐣ワ紝渚嬪锛?

- `website/python-a/deepseek.local.json`
- `website/quant-a/data/`
- `website/video/config/config.local.json`
- `website/video/anime_projects/`
- `.env`銆乣.venv/`銆乣__pycache__/`銆乣.pytest_cache/`銆乣*.log`

## 鏂囨。缁存姢瑙勫垯

姣忔淇敼椤圭洰缁撴瀯銆佹ā鍧楄亴璐ｃ€佸惎鍔ㄥ懡浠ゃ€佺鍙ｃ€侀厤缃」銆丄PI銆佹暟鎹洰褰曘€佹祴璇曟柟寮忔垨閮ㄧ讲鍏ュ彛鏃讹紝蹇呴』鍚屾鏇存柊鏍?`AGENTS.md` / `README.md`锛屼互鍙婂彈褰卞搷妯″潡鎴栧井搴旂敤鐩綍涓嬬殑 `AGENTS.md` / `README.md`銆傛枃妗ｅ拰浠ｇ爜涓嶄竴鑷存椂锛屾湰娆℃敼鍔ㄤ笉鑳借涓哄畬鎴愩€?

寮€鍙戜唬鐞嗙粏鑺傘€佹ā鍧楄竟鐣屻€丄PI 娓呭崟鍜屾祴璇曡姹傝鏍圭洰褰?`AGENTS.md`锛屾ā鍧楃洰褰曚笅鐨?`AGENTS.md` / `README.md` 浠ュ悇鑷ā鍧椾负鍑嗐€?

