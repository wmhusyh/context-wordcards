"""独立构建 APK，无 Gradle 依赖。Python 3 + JDK + 官方 Android Build Tools 35 / Platform 35。"""
import argparse
from pathlib import Path
import subprocess
import zipfile
import shutil

parser = argparse.ArgumentParser()
parser.add_argument('--java', required=True, help='JDK 根目录')
parser.add_argument('--tools', required=True, help='含 aapt2.exe 的 Build Tools 目录')
parser.add_argument('--platform', required=True, help='含 android.jar 的 Platform 目录')
parser.add_argument('--work', required=True, help='构建中间文件目录')
parser.add_argument('--out', required=True, help='APK 输出路径')
args = parser.parse_args()
root = Path(__file__).resolve().parent
java, tools, platform = [Path(v).resolve() for v in (args.java,args.tools,args.platform)]
work = Path(args.work).resolve(); work.mkdir(parents=True,exist_ok=True)
source = root / 'app/src/main'
classes = work / 'classes'; classes.mkdir(exist_ok=True)
dex = work / 'dex'; dex.mkdir(exist_ok=True)
output = Path(args.out).resolve(); output.parent.mkdir(parents=True,exist_ok=True)

def run(*cmd):
    subprocess.run([str(c) for c in cmd], check=True)

run(java/'bin/javac.exe', '-encoding','UTF-8','-source','8','-target','8','-classpath',platform/'android.jar','-d',classes,*source.rglob('*.java'))
run(tools/'aapt2.exe','compile','--dir',source/'res','-o',work/'resources.zip')
manifest = work / 'AndroidManifest.xml'
manifest.write_text((source/'AndroidManifest.xml').read_text(encoding='utf-8').replace('<manifest ', '<manifest package="com.gongdi.wordcards" ', 1), encoding='utf-8')
run(tools/'aapt2.exe','link','-o',work/'resources.apk','--manifest',manifest,'-I',platform/'android.jar','-A',source/'assets',work/'resources.zip')
run(java/'bin/java.exe','-cp',tools/'lib/d8.jar','com.android.tools.r8.D8','--release','--min-api','26','--lib',platform/'android.jar','--output',dex,*classes.rglob('*.class'))
with zipfile.ZipFile(work/'resources.apk') as source_apk, zipfile.ZipFile(work/'unsigned.apk','w',zipfile.ZIP_DEFLATED) as dest:
    for entry in source_apk.infolist(): dest.writestr(entry,source_apk.read(entry.filename))
    for path in dex.glob('*.dex'): dest.write(path,path.name)
run(tools/'zipalign.exe','-f','4',work/'unsigned.apk',work/'aligned.apk')
# 开发签名只用于个人安装，密钥保留在指定 work 目录，以便后续覆盖升级。
keystore=work/'wordcards-development.jks'
if not keystore.exists():
    run(java/'bin/keytool.exe','-genkeypair','-keystore',keystore,'-storepass','android','-keypass','android','-alias','wordcards','-keyalg','RSA','-keysize','2048','-validity','10000','-dname','CN=WordCards Personal Development','-storetype','JKS')
signed = work / 'wordcards-signed.apk'
run(java/'bin/java.exe','-jar',tools/'lib/apksigner.jar','sign','--ks',keystore,'--ks-key-alias','wordcards','--ks-pass','pass:android','--key-pass','pass:android','--out',signed,work/'aligned.apk')
run(java/'bin/java.exe','-jar',tools/'lib/apksigner.jar','verify','--verbose',signed)
run(tools/'aapt.exe','dump','badging',signed)
shutil.copyfile(signed, output)
print('APK ready:', output)
