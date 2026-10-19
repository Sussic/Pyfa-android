package io.github.sussic.pyfa

import android.content.Context
import android.net.Uri
import android.provider.OpenableColumns
import android.util.AtomicFile
import java.io.ByteArrayOutputStream
import java.io.File
import java.nio.ByteBuffer
import java.nio.charset.CodingErrorAction
import org.json.JSONArray
import org.json.JSONObject

data class OfflineEftDocument(val label: String, val text: String)
data class OfflineImportDiagnostic(val document: Int?, val label: String?, val line: Int, val code: String, val message: String)
data class OfflineImportDocument(val label: String, val index: Int, val name: String?, val hull: String?, val lines: List<String>)
data class OfflineImportPreview(val requestId: String, val ok: Boolean, val exactRequest: String?,
    val documents: List<OfflineImportDocument>, val diagnostics: List<OfflineImportDiagnostic>)
data class OfflineImportResult(val requestId: String, val ok: Boolean, val committed: Boolean?, val reopenRequired: Boolean,
    val replayed: Boolean, val fitIds: List<String>, val missingFitIds: List<String>, val diagnostics: List<OfflineImportDiagnostic>,
    val state: OfflineFeatureState?, val bridge: BridgeResponse?)

internal object OfflineImportCodec {
    private val codec get() = OfflineFeatureCodec
    fun request(raw: String): JSONObject {
        val root = codec.parse(raw)
        codec.keys(root, "version", "operation", "request_id", "dataset", "graph", "profile", "documents")
        codec.expect(codec.integer(root.get("version")) == 1L && codec.text(root.get("operation")) == "import_eft", "invalid import version")
        codec.expect(codec.text(root.get("request_id")).matches(Regex("[A-Za-z0-9_-]{1,128}")), "invalid import identity")
        codec.expect(codec.text(root.get("dataset")).matches(Regex("[0-9a-f]{64}")), "invalid import dataset")
        val graph = codec.obj(root.get("graph")); codec.keys(graph, "generation", "token")
        codec.expect(codec.integer(graph.get("generation")) >= 1 && codec.text(graph.get("token")).matches(Regex("[0-9a-f]{32}")), "invalid import graph")
        val profile = codec.obj(root.get("profile")); codec.keys(profile, "id", "revision")
        codec.identity(profile.get("id")); codec.expect(codec.integer(profile.get("revision")) >= 0, "invalid import profile")
        val documents = codec.rows(root.get("documents")); codec.expect(documents.size in 1..16, "invalid document count")
        var bytes = 0L
        for (rawDocument in documents) {
            val document = codec.obj(rawDocument); codec.keys(document, "label", "text")
            codec.identity(document.get("label"))
            bytes += codec.text(document.get("text")).toByteArray(Charsets.UTF_8).size
        }
        codec.expect(bytes <= 1024 * 1024, "EFT text exceeds one MiB")
        return root
    }
    private fun diagnostics(raw: Any): List<OfflineImportDiagnostic> = codec.frozen(codec.rows(raw).map { entry ->
        val row = codec.obj(entry); codec.keys(row, "document", "label", "line", "code", "message")
        val index = row.get("document").let { if (it === JSONObject.NULL) null else codec.integer(it).also { n -> codec.expect(n in 0..15, "invalid document index") }.toInt() }
        val line = codec.integer(row.get("line")); codec.expect(line in 0..Int.MAX_VALUE.toLong(), "invalid source line")
        OfflineImportDiagnostic(index, codec.nullableText(row.get("label")), line.toInt(), codec.text(row.get("code")), codec.text(row.get("message")))
    })
    fun preview(raw: String, requestId: String, expected: JSONObject): OfflineImportPreview {
        val root = codec.parse(raw); codec.keys(root, "version", "request_id", "ok", "request", "documents", "diagnostics")
        val ok = codec.bool(root.get("ok"))
        val replyId = codec.nullableText(root.get("request_id"))
        codec.expect(codec.integer(root.get("version")) == 1L && (replyId == requestId || !ok && replyId == null), "preview identity differs")
        val diagnostics = diagnostics(root.get("diagnostics"))
        val exact = if (root.get("request") === JSONObject.NULL) null else codec.json(root.get("request"))
        codec.expect(ok == (exact != null) && (!ok || diagnostics.isEmpty()), "inconsistent import preview")
        if (exact != null) {
            val checked = request(exact)
            codec.expect(checked.getString("request_id") == requestId && checked.getJSONObject("profile").getString("id") == expected.getString("profile_id"), "preview request differs")
            val actualDocs = codec.rows(checked.get("documents")).map { codec.obj(it).let { doc -> doc.getString("label") to doc.getString("text") } }
            val expectedDocs = codec.rows(expected.get("documents")).map { codec.obj(it).let { doc -> doc.getString("label") to doc.getString("text") } }
            codec.expect(actualDocs == expectedDocs, "preview changed original source")
        }
        val documents = codec.rows(root.get("documents")).map { entry ->
            val row = codec.obj(entry); codec.keys(row, "header", "tokens", "label", "document")
            val index = codec.integer(row.get("document")); codec.expect(index in 0..15, "invalid preview index")
            val header = row.get("header").let { if (it === JSONObject.NULL) null else codec.obj(it) }
            val lines = codec.rows(row.get("tokens")).map { token ->
                val value = codec.obj(token)
                val line = codec.integer(value.get("line")); val section = codec.integer(value.get("section"))
                codec.expect(line >= 1 && section >= 0 && codec.text(value.get("kind")) in setOf("item", "quantity", "empty", "invalid"), "invalid preview token")
                "Line $line · section ${section + 1}: ${codec.text(value.get("text"))}"
            }
            OfflineImportDocument(codec.text(row.get("label")), index.toInt(), header?.let { codec.text(it.get("name")) },
                header?.let { codec.text(it.get("ship")) }, codec.frozen(lines))
        }
        codec.expect(documents.map { it.index }.distinct().size == documents.size, "duplicate preview document")
        return OfflineImportPreview(requestId, ok, exact, codec.frozen(documents), diagnostics)
    }
    fun result(raw: String, requestId: String, sessionId: String, expectedRequest: JSONObject): OfflineImportResult {
        val root = codec.parse(raw); codec.keys(root, "version", "request_id", "ok", "committed", "reopen_required", "import_result", "state", "bridge")
        codec.expect(codec.integer(root.get("version")) == 1L && codec.text(root.get("request_id")) == requestId, "import response identity differs")
        val ok = codec.bool(root.get("ok")); val reopen = codec.bool(root.get("reopen_required"))
        val committed = root.get("committed").let { if (it === JSONObject.NULL) null else codec.bool(it) }
        codec.expect(if (ok) committed == true && !reopen else committed != true && (committed == null) == reopen, "ambiguous import outcome")
        val result = codec.obj(root.get("import_result"))
        if (ok) codec.keys(result, "version", "operation", "ok", "import_committed", "reopen_required", "replayed", "receipt", "fit_ids", "missing_fit_ids", "current_graph", "diagnostics")
        else codec.keys(result, "version", "operation", "ok", "import_committed", "reopen_required", "replayed", "fit_ids", "diagnostics")
        val innerCommitted = result.get("import_committed").let { if (it === JSONObject.NULL) null else codec.bool(it) }
        codec.expect(innerCommitted == committed && codec.bool(result.get("reopen_required")) == reopen, "contradictory import outcome")
        codec.expect(codec.integer(result.get("version")) == 1L && codec.text(result.get("operation")) == "import_eft" && codec.bool(result.get("ok")) == ok, "invalid import result")
        val ids = codec.rows(result.get("fit_ids")).map(codec::identity)
        val missing = if (result.has("missing_fit_ids")) codec.rows(result.get("missing_fit_ids")).map(codec::identity) else emptyList()
        codec.expect(ids.distinct().size == ids.size && missing.distinct().size == missing.size && ids.containsAll(missing), "invalid imported identities")
        val state = if (ok) codec.state(codec.obj(root.get("state"))) else null
        val bridge = if (ok) BridgeCodec.decodeResponse(codec.json(root.get("bridge"))) else null
        if (ok) {
            val readyState = checkNotNull(state)
            val readyBridge = checkNotNull(bridge)
            val receipt = codec.obj(result.get("receipt")); codec.keys(receipt, "fingerprint", "fit_ids", "names", "fit_revisions", "generation")
            codec.expect(codec.text(receipt.get("fingerprint")).matches(Regex("[0-9a-f]{64}")), "invalid import fingerprint")
            val receiptIds = codec.rows(receipt.get("fit_ids")).map(codec::identity)
            val names = codec.rows(receipt.get("names")).map(codec::text)
            val revisions = codec.rows(receipt.get("fit_revisions")).map(codec::integer)
            codec.expect(ids == receiptIds && ids.size == expectedRequest.getJSONArray("documents").length() && ids.size in 1..16 && ids.all { it.matches(Regex("[0-9a-f]{32}")) }, "inconsistent receipt identities")
            codec.expect(names.size == ids.size && names.all { it.isNotBlank() } && revisions.size == ids.size && revisions.all { it == 1L }, "invalid receipt inputs")
            val receiptGeneration = codec.integer(receipt.get("generation"))
            val current = codec.obj(result.get("current_graph")); codec.keys(current, "generation", "token")
            codec.expect(codec.text(current.get("token")).matches(Regex("[0-9a-f]{32}")), "invalid current graph identity")
            codec.expect(receiptGeneration > codec.integer(expectedRequest.getJSONObject("graph").get("generation")) && receiptGeneration <= codec.integer(current.get("generation")), "invalid receipt generation")
            codec.expect(codec.integer(current.get("generation")) == readyState.context.generation && readyState.context.datasetSha256 == expectedRequest.getString("dataset"), "receipt graph differs")
            codec.expect(codec.bool(result.get("replayed")) || missing.isEmpty(), "new import has missing fits")
            codec.expect(readyState.context.sessionId == sessionId && readyBridge.isSuccess && readyBridge.requestId == "bootstrap" && readyBridge.sessionId == sessionId, "invalid imported library")
            codec.validateLibrary(readyState, readyBridge)
            codec.expect(ids.filter { it !in readyState.bindings } == missing, "missing import identities differ")
        } else {
            codec.expect(root.get("state") === JSONObject.NULL && root.get("bridge") === JSONObject.NULL && ids.isEmpty() && !codec.bool(result.get("replayed")), "failed import published fits")
            codec.expect(codec.rows(result.get("diagnostics")).isNotEmpty(), "missing import failure diagnosis")
        }
        return OfflineImportResult(requestId, ok, committed, reopen, codec.bool(result.get("replayed")), codec.frozen(ids),
            codec.frozen(missing), diagnostics(result.get("diagnostics")), state, bridge)
    }
}

/** Owns exactly one unresolved request. Read failures preserve the original bytes. */
internal class OfflineImportStore(private val path: File) {
    private val file = AtomicFile(path)
    fun load(): String? {
        if (!path.exists() && !File(path.path + ".bak").exists()) return null
        return file.openRead().use { stream ->
            val bytes = stream.readBytesBounded(8 * 1024 * 1024)
            strictUtf8(bytes).also { OfflineImportCodec.request(it) }
        }
    }
    fun save(exactRequest: String) {
        OfflineImportCodec.request(exactRequest)
        val previous = load()
        check(previous == null || previous == exactRequest) { "Resolve the earlier import before starting another." }
        if (previous != null) return
        check(path.parentFile!!.isDirectory || path.parentFile!!.mkdirs())
        val stream = file.startWrite()
        try { stream.write(exactRequest.toByteArray(Charsets.UTF_8)); file.finishWrite(stream) }
        catch (failure: Exception) { file.failWrite(stream); throw failure }
        check(load() == exactRequest) { "Could not confirm the saved retry record." }
    }
    fun clear() { file.delete(); check(!path.exists() && !File(path.path + ".bak").exists()) }
}

private fun java.io.InputStream.readBytesBounded(limit: Int): ByteArray {
    val out = ByteArrayOutputStream(); val buffer = ByteArray(8192)
    while (true) {
        val count = read(buffer); if (count < 0) break
        check(out.size() + count <= limit) { "EFT input exceeds the allowed size." }
        out.write(buffer, 0, count)
    }
    return out.toByteArray()
}
private fun strictUtf8(bytes: ByteArray): String = Charsets.UTF_8.newDecoder()
    .onMalformedInput(CodingErrorAction.REPORT).onUnmappableCharacter(CodingErrorAction.REPORT)
    .decode(ByteBuffer.wrap(bytes)).toString()

internal object OfflineImportFiles {
    fun read(context: Context, uris: List<Uri>): List<OfflineEftDocument> {
        require(uris.size in 1..16) { "Select one to sixteen EFT text files." }
        var remaining = 1024 * 1024
        return uris.mapIndexed { index, uri ->
            val label = context.contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { cursor ->
                if (cursor.moveToFirst()) cursor.getString(0) else null
            }?.take(200)?.takeIf { it.isNotBlank() && it.none { c -> c.code < 32 } } ?: "File ${index + 1}"
            val bytes = checkNotNull(context.contentResolver.openInputStream(uri)).use { it.readBytesBounded(remaining) }
            remaining -= bytes.size
            OfflineEftDocument(label, strictUtf8(bytes))
        }
    }
}
