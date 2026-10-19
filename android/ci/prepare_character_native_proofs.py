"""C07.2 actual Kotlin preparation only. Never starts a JVM, EOS, download or build.

Usage: python android/ci/prepare_character_native_proofs.py /absolute/new/output
The parent owns fresh admission and the exclusive heavy lane before run.sh.
"""
from pathlib import Path
import hashlib
import json
import re
import sys

REPO = Path(__file__).resolve().parents[2]
SRC = REPO / 'android/app/src/main/java/io/github/sussic/pyfa'
TEST = REPO / 'android/app/src/androidTest/java/io/github/sussic/pyfa'
OUT = Path(sys.argv[1]).resolve()
if not OUT.is_absolute() or OUT.exists():
    raise SystemExit('Use a new absolute task-local output directory; no overwrite is allowed.')
OUT.mkdir(parents=True)
sources = {Path(__file__).resolve()}
def read(path):
    sources.add(path)
    return path.read_text()
def segment(text, first, after):
    return text[text.index(first):text.index(after, text.index(first))]
def write(name, value):
    (OUT / name).write_text(value)
def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()
bridge = read(SRC / 'BridgeContract.kt')
slot = segment(read(SRC / 'FittingDetails.kt'), 'enum class ModuleSlot', 'data class ResourceUse')
types = segment(bridge, '/** Keep integer, decimal', 'object BridgeCodec {')
response = segment(bridge, '    fun decodeResponse(json: String)', '    fun decodeFitSpec(json: String)')
fit = segment(bridge, '    private fun decodeFit(raw: Any', '    fun decodeRecent(json: String)')
helpers = bridge[bridge.index('    private val STAT_NAMES ='):]
write('BridgeSupport.kt', 'package io.github.sussic.pyfa\nimport org.json.JSONObject\nimport org.json.JSONArray\nimport java.util.Collections\n'
      + 'enum class ModuleState { OFFLINE, ONLINE, ACTIVE, OVERHEATED }\n' + slot + types
      + 'object BridgeCodec {\n    const val VERSION = 1\n' + response + fit + helpers)
for name in ('OfflineFeaturesContract.kt', 'ImplantDetails.kt', 'CharacterImplantCatalog.kt'):
    write(name, read(SRC / name))
model = read(SRC / 'OfflineFeaturesProfiles.kt')
write('OfflineProfilesModel.kt', 'package io.github.sussic.pyfa\nimport android.content.Context\nimport androidx.compose.runtime.*\nimport androidx.core.content.ContextCompat\nimport androidx.lifecycle.ViewModel\nimport org.json.JSONObject\n'
      + segment(model, 'enum class OfflineProfileSection', '@Composable'))
imports = read(SRC / 'OfflineFeaturesImportContract.kt')
write('OfflineImportCodec.kt', 'package io.github.sussic.pyfa\nimport org.json.JSONArray\nimport org.json.JSONObject\n'
      + segment(imports, 'data class OfflineEftDocument', '/** Owns exactly one'))
engine = read(SRC / 'EngineRuntime.kt')
write('EngineStub.kt', '''package io.github.sussic.pyfa
import android.content.Context
import java.util.concurrent.CompletableFuture
import org.json.JSONObject
''' + segment(engine, 'sealed interface EngineState', '/** One process-owned worker') + '''
class HostValue<T>(val value:T)
object EngineRuntime {
    val offlineFeatures=HostValue<OfflineFeatureState?>(null)
    val state=HostValue<EngineState>(EngineState.Loading)
    fun offlineFeatureState(context:Context, fit:String?):CompletableFuture<OfflineFeatureState> = error("Uninjected engine call is forbidden in host checks")
    fun offlineFeatureRequest(context:Context, expected:OfflineContext, operation:String, args:JSONObject, anchor:String?):CompletableFuture<OfflineFeatureResponse> = error("Uninjected engine call is forbidden in host checks")
}
''')
write('ContextStub.kt', 'package android.content\nopen class Context { val applicationContext:Context get()=this }\n')
write('ExecutorStub.kt', '''package androidx.core.content
import android.content.Context
import java.util.concurrent.Executor
object ContextCompat { fun getMainExecutor(context:Context):Executor = Executor { it.run() } }
''')
write('ComposeStub.kt', '''package androidx.compose.runtime
import kotlin.reflect.KProperty
class MutableState<T>(var value:T)
fun <T> mutableStateOf(value:T)=MutableState(value)
operator fun <T> MutableState<T>.getValue(owner:Any?, property:KProperty<*>):T=value
operator fun <T> MutableState<T>.setValue(owner:Any?, property:KProperty<*>, next:T){value=next}
''')
write('LifecycleStub.kt', '''package androidx.lifecycle
open class ViewModel { protected open fun onCleared() {}; fun hostClear(){onCleared()} }
class ViewModelStore {
    private val models=mutableMapOf<String,ViewModel>()
    fun put(key:String, model:ViewModel){models[key]=model}
    fun clear(){models.values.forEach{it.hostClear()};models.clear()}
}
''')
write('InstrumentationStub.kt', '''package androidx.test.platform.app
import android.content.Context
class HostInstrumentation {
    val targetContext=Context()
    fun runOnMainSync(action:()->Unit){action()}
    fun waitForIdleSync(){}
}
object InstrumentationRegistry {private val value=HostInstrumentation();fun getInstrumentation()=value}
''')
test_classes = ('OfflineFeaturesContractTest', 'CharacterImplantsContractTest', 'CharacterImplantsModelTest', 'CharacterImplantsImportContractTest')
methods = {}
for name in test_classes:
    text = read(TEST / (name + '.kt'))
    methods[name] = re.findall(r'@Test\s+fun\s+(\w+)', text)
    write(name + '.kt', text.replace('import androidx.test.ext.junit.runners.AndroidJUnit4\n', '').replace('@RunWith(AndroidJUnit4::class)\n', ''))
write('run.sh', '''#!/bin/bash
set -euo pipefail
[[ "${1-}" == "--compile" || "${1-}" == "--tests" ]] || { echo 'Prepared only. Parent fresh admission and exclusive lane are required.'; exit 2; }
cd "$(dirname "$0")"
LIB=/workspace/shared/pyfa-native-build-20261017/tools/gradle-8.13/lib
JAVA=/workspace/shared/pyfa-native-build-20261017/tools/jdk/bin/java
CACHE=/workspace/shared/pyfa-native-build-20261017/gradle-cache/caches/modules-2/files-2.1
JSON=$CACHE/org.json/json/20160810/aca5eb39e2a12fddd6c472b240afe9ebea3a6733/json-20160810.jar
JUNIT=$CACHE/junit/junit/4.13.2/8ac9e16d933b6fb43bc7f576336b8f4d7eb5ba12/junit-4.13.2.jar
HAMCREST=$CACHE/org.hamcrest/hamcrest-core/1.3/42a25dc3219429f0e5d060061f71acb49bf010a0/hamcrest-core-1.3.jar
CP="$LIB/kotlin-stdlib-2.0.21.jar:$JSON:$JUNIT:$HAMCREST"
COMPILER_CP="$LIB/kotlin-compiler-embeddable-2.0.21.jar:$LIB/kotlin-stdlib-2.0.21.jar:$LIB/kotlin-script-runtime-2.0.21.jar:$LIB/kotlin-reflect-2.0.21.jar:$LIB/kotlin-daemon-embeddable-2.0.21.jar:$LIB/trove4j-1.0.20200330.jar:$LIB/kotlinx-coroutines-core-jvm-1.6.4.jar:$LIB/annotations-24.0.1.jar"
PYTHON=/workspace/shared/pyfa-native-build-20261017/tools/venv/bin/python
"$PYTHON" -I -B - <<'VERIFY' 
import hashlib,json,pathlib
manifest=json.loads(pathlib.Path('manifest.json').read_text())
def digest(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
for section in ('sources','prepared_files','tool_inputs'):
    for key,value in manifest[section].items():
        path=pathlib.Path(key)
        if not path.is_file() or digest(path)!=value:raise SystemExit('Binding mismatch: '+section+': '+key)
actual={p.name for p in pathlib.Path('.').iterdir() if p.suffix in ('.kt','.sh')}
if actual!=set(manifest['prepared_files']):raise SystemExit('Prepared source membership differs')
print('Exact source/prepared bindings match.')
VERIFY
if [[ "$1" == --compile ]]; then
  [[ ! -e classes ]] || { echo 'Use a new prepared attempt directory.'; exit 2; }
  mkdir classes
  timeout --foreground -k 5s 90s "$JAVA" -Xmx256m -XX:MaxMetaspaceSize=192m -cp "$COMPILER_CP" org.jetbrains.kotlin.cli.jvm.K2JVMCompiler -no-stdlib -no-reflect -classpath "$CP" -d classes *.kt
  "$PYTHON" -I -B - <<'CLASS_BIND'
import hashlib,json,pathlib
rows={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in pathlib.Path('classes').rglob('*') if p.is_file()}
if not rows:raise SystemExit('Compiler returned no output')
pathlib.Path('compiled-manifest.json').write_text(json.dumps(rows,sort_keys=True,indent=2)+'\\n')
CLASS_BIND
else
  "$PYTHON" -I -B - <<'CLASS_CHECK'
import hashlib,json,pathlib
expected=json.loads(pathlib.Path('compiled-manifest.json').read_text())
actual={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in pathlib.Path('classes').rglob('*') if p.is_file()}
if actual!=expected:raise SystemExit('Compiled classes changed before tests')
CLASS_CHECK
  timeout --foreground -k 5s 45s "$JAVA" -Xmx256m -XX:MaxMetaspaceSize=128m -cp "classes:$CP" org.junit.runner.JUnitCore ''' + ' '.join('io.github.sussic.pyfa.' + name for name in test_classes) + '''
fi
''')
# Wire-consumer preparation is deliberately separate and waits for a terminal candidate bundle.
TOOLS = Path('/workspace/shared/pyfa-native-build-20261017/tools')
LIB = TOOLS / 'gradle-8.13/lib'
CACHE = TOOLS.parent / 'gradle-cache/caches/modules-2/files-2.1'
python = TOOLS / 'venv/bin/python'
if digest(python) != 'a2886d92ebf115fde6eb05569bda5ce2d09113adad3264a267b29f7dbff2c076':
    raise SystemExit('Pinned verification interpreter changed')
tool_paths = [python, python.resolve(), TOOLS / 'jdk/bin/java', TOOLS / 'jdk/lib/server/libjvm.so', TOOLS / 'jdk/lib/modules', TOOLS / 'jdk/release']
tool_paths += [LIB / name for name in ('kotlin-compiler-embeddable-2.0.21.jar', 'kotlin-stdlib-2.0.21.jar', 'kotlin-script-runtime-2.0.21.jar',
    'kotlin-reflect-2.0.21.jar', 'kotlin-daemon-embeddable-2.0.21.jar', 'trove4j-1.0.20200330.jar', 'kotlinx-coroutines-core-jvm-1.6.4.jar', 'annotations-24.0.1.jar')]
tool_paths += [CACHE / name for name in ('org.json/json/20160810/aca5eb39e2a12fddd6c472b240afe9ebea3a6733/json-20160810.jar',
    'junit/junit/4.13.2/8ac9e16d933b6fb43bc7f576336b8f4d7eb5ba12/junit-4.13.2.jar', 'org.hamcrest/hamcrest-core/1.3/42a25dc3219429f0e5d060061f71acb49bf010a0/hamcrest-core-1.3.jar')]
manifest = dict(qualification='Actual unchanged feature/catalogue/implant codecs, extracted unchanged profile model and import codec, actual unchanged bridge bootstrap/fit decoder and StrictJson parser. Only AndroidJUnit4 annotations/imports removed from tests. Synchronous minimal Context/main executor/Compose state/lifecycle/instrumentation stubs. No rendering, Android scheduling, EOS, store integration or native execution claim.',
    sources={str(path): digest(path) for path in sorted(sources)},
    prepared_files={path.name: digest(path) for path in sorted(OUT.iterdir()) if path.suffix in ('.kt', '.sh')},
    tool_inputs={str(path):digest(path) for path in sorted(set(tool_paths))},
    test_methods=methods, method_count=sum(map(len, methods.values())), executed=False)
(OUT / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
print(json.dumps(dict(prepared=True, executed=False, output=str(OUT), method_count=manifest['method_count'], manifest_sha256=digest(OUT / 'manifest.json'))))
