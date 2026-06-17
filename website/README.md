# website

`website` 鏄?`love530` 鑱氬悎宸ョ▼涓殑涓汉涓婚〉/灞曠ず绔欑偣 Web 鏈嶅姟锛岄粯璁ょ鍙?`8080`銆傚畠鍚屾椂璐熻矗鎻愪緵鍗氬銆佹彁绀鸿瘝鎺у埗鍙般€侀潤鎬侀椤靛叆鍙ｏ紝浠ュ強 `python-a`銆乣quant-a`銆乣video` 涓変釜鐙珛 Python 瀛愭湇鍔＄殑鑷姩鍚姩鍜屽仴搴锋鏌ャ€?

## 鍔熻兘

- 涓汉涓婚〉闈欐€佺珯鐐广€?
- 鍗氬 API 鍜屽墠绔〉闈€?
- 鎻愮ず璇嶆帶鍒跺彴鍜岄潤鎬佹彁绀鸿瘝搴撻〉闈€?
- `python-a`銆乣quant-a`銆乣video` 鐨勫叆鍙ｃ€佸仴搴锋娴嬪拰鑷姩鍚姩銆?
- Web銆丱SS銆丯acos Discovery 绀轰緥浠ｇ爜銆?

## 杩愯

```bash
mvn -pl website -am spring-boot:run
```

璁块棶锛?

```text
http://localhost:8080/
```

鐩存帴鍚姩 `website` 鏃讹紝浼氶粯璁ゆ鏌ュ苟鎷夎捣锛?

```text
http://127.0.0.1:5174/api/health  python-a
http://127.0.0.1:5175/api/health  quant-a
http://127.0.0.1:5176/api/health  video
```

## 涓昏鐩綍

```text
src/main/java/com/example/website/
  auth/         common 璁よ瘉閫傞厤
  blog/         鍗氬 API
  demos/        绀轰緥浠ｇ爜
  integration/  Python 瀛愭湇鍔¤嚜鍔ㄥ惎鍔?
  prompt/       鎻愮ず璇嶆帶鍒跺彴鍚庣
src/main/resources/static/
  index.html
  blog/
  css/
  js/
  media/
  prompt-console/
python-a/
quant-a/
video/
```

## 娴嬭瘯

```bash
mvn -pl website -am test
```

鎻愮ず璇嶅簱闈欐€佸垎绫婚€昏緫鍙崟鐙獙璇侊細

```bash
node website/src/test/js/prompt-console/prompt-category-groups.test.js
```

`src/main/resources/static/prompt-console/prompt-category-groups.js` 缁存姢鈥滄彁绀鸿瘝澶у垎绫?-> 灏忓垎绫烩€濈殑鏄犲皠銆傚綋鍓嶉〉闈細鍏堟寜澶у垎绫荤瓫閫夛紝鍐嶆寜灏忓垎绫荤粏鍒嗭紱鏂板鎻愮ず璇嶅皬绫绘椂浼樺厛琛ュ厖璇ユ槧灏勶紝鏈槧灏勭殑灏忕被浼氳嚜鍔ㄨ繘鍏モ€滃叾浠栤€濄€?
淇敼 Python 瀛愭湇鍔¤嚜鍔ㄥ惎鍔ㄩ€昏緫鏃讹紝鑷冲皯杩愯瀵瑰簲鐨?`PythonAAutoStartRunnerTest`銆乣QuantAAutoStartRunnerTest` 鎴?`VideoAutoStartRunnerTest`銆傛祴璇曞繀椤诲叧闂閮ㄥ瓙杩涚▼鑷姩鍚姩銆?
## 鏂囨。缁存姢

姣忔淇敼棣栭〉鍏ュ彛銆佹彁绀鸿瘝鎺у埗鍙般€佸崥瀹€佽嚜鍔ㄥ惎鍔ㄩ厤缃€丳ython 瀛愭湇鍔￠泦鎴愩€佺鍙ｃ€丄PI銆侀潤鎬佽祫婧愮洰褰曟垨娴嬭瘯鏂瑰紡鏃讹紝蹇呴』鍚屾鏇存柊 `website/AGENTS.md`銆佹湰 README锛屼互鍙婃牴鐩綍 `AGENTS.md` / `README.md` 涓浉鍏冲唴瀹广€?

