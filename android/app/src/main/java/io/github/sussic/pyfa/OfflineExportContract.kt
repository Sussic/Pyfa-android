package io.github.sussic.pyfa

import org.json.JSONObject

data class OfflineExportOptions(val loadedCharges: Boolean = true, val cargo: Boolean = true,
    val implants: Boolean = true, val boosters: Boolean = true, val mutations: Boolean = true) {
    fun json(): JSONObject = JSONObject().put("loaded_charges", loadedCharges).put("cargo", cargo)
        .put("implants", implants).put("boosters", boosters).put("mutations", mutations)
}
data class OfflineExportRequest(val requestId: String, val context: OfflineContext, val fitId: String,
    val revision: Long, val options: OfflineExportOptions) {
    fun json(): String {
        require(requestId.isNotBlank() && requestId.length <= 128 && fitId.isNotBlank() && revision >= 1)
        return OfflineFeatureCodec.json(JSONObject().put("version", 1).put("request_id", requestId)
            .put("context", context.json()).put("fit_id", fitId).put("revision", revision).put("options", options.json()))
    }
}
data class OfflineExportDiagnostic(val code: String, val message: String)
data class OfflineExportPreview(val request: OfflineExportRequest, val ok: Boolean, val text: String?,
    val filename: String?, val diagnostics: List<OfflineExportDiagnostic>, val error: OfflineFeatureError?) {
    internal val requiresEngineReopen: Boolean get() = !ok && error?.code in setOf("reopen_required", "engine_unavailable")
}

/** Export is read-only. No malformed, stale or failed response exposes output text. */
internal object OfflineExportCodec {
    private val codec get() = OfflineFeatureCodec
    fun options(raw: String): OfflineExportOptions {
        val row = codec.parse(raw)
        codec.keys(row, "loaded_charges", "cargo", "implants", "boosters", "mutations")
        return OfflineExportOptions(codec.bool(row.get("loaded_charges")), codec.bool(row.get("cargo")),
            codec.bool(row.get("implants")), codec.bool(row.get("boosters")), codec.bool(row.get("mutations")))
    }
    fun preview(raw: String, expected: OfflineExportRequest): OfflineExportPreview {
        val row = codec.parse(raw)
        codec.keys(row, "version", "request_id", "ok", "context", "fit_id", "revision", "text", "filename", "diagnostics", "error")
        codec.expect(codec.integer(row.get("version")) == 1L, "unsupported export version")
        val ok = codec.bool(row.get("ok"))
        val requestId = codec.nullableText(row.get("request_id"))
        codec.expect(requestId == expected.requestId || !ok && requestId == null, "export response identity differs")
        val context = row.get("context").let { if (it === JSONObject.NULL) null else codec.context(codec.obj(it)) }
        val fitId = codec.nullableText(row.get("fit_id"))
        val revision = row.get("revision").let { if (it === JSONObject.NULL) null else codec.integer(it).also { n -> codec.expect(n >= 1, "invalid export revision") } }
        codec.expect(fitId == null || fitId == expected.fitId, "export fit identity differs")
        codec.expect(revision == null || revision == expected.revision, "export revision differs")
        val diagnostics = codec.rows(row.get("diagnostics")).map { entry ->
            val value = codec.obj(entry); codec.keys(value, "code", "message")
            OfflineExportDiagnostic(codec.text(value.get("code")).also { codec.expect(it.isNotBlank(), "empty diagnostic code") },
                codec.text(value.get("message")).also { codec.expect(it.isNotBlank(), "empty diagnostic message") })
        }
        val text = codec.nullableText(row.get("text"))
        val filename = codec.nullableText(row.get("filename"))
        if (!ok) {
            codec.expect(text == null && filename == null, "failed export contains usable text")
            val error = codec.obj(row.get("error")); codec.keys(error, "code", "message")
            return OfflineExportPreview(expected, false, null, null, codec.frozen(diagnostics),
                OfflineFeatureError(codec.text(error.get("code")).also { codec.expect(it.isNotBlank(), "empty export error code") },
                    codec.text(error.get("message")).also { codec.expect(it.isNotBlank(), "empty export error") }))
        }
        codec.expect(row.get("error") === JSONObject.NULL && context == expected.context && fitId == expected.fitId && revision == expected.revision,
            "successful export is stale or inconsistent")
        codec.expect(!text.isNullOrBlank() && text.toByteArray(Charsets.UTF_8).size <= 1024 * 1024, "empty or oversized export")
        codec.expect(text!!.none { it.code < 32 && it !in "\r\n\t" || it.code in 127..159 }, "invalid export control character")
        codec.expect(filename != null && filename.length > 4 && filename.codePointCount(0, filename.length) <= 200 && filename.endsWith(".txt") &&
            filename.none { it == '/' || it == '\\' || it.code < 32 || it.code in 127..159 }, "unsafe export filename")
        return OfflineExportPreview(expected, true, text, filename, codec.frozen(diagnostics), null)
    }
}
