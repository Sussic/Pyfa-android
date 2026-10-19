package io.github.sussic.pyfa

data class SystemSecurityChoice(val id: SystemSecurity, val label: String)
data class SystemSecurityDetails(val fitId: String, val revision: Long, val isStructure: Boolean,
    val system: SystemSecurity, val choices: List<SystemSecurityChoice>)

internal object SystemSecurityCodec {
    private val sourceChoices = listOf(
        SystemSecurityChoice(SystemSecurity.HISEC, "High Security"),
        SystemSecurityChoice(SystemSecurity.LOWSEC, "Low Security"),
        SystemSecurityChoice(SystemSecurity.NULLSEC, "Null Security"),
        SystemSecurityChoice(SystemSecurity.WSPACE, "W-Space"))
    private fun system(raw: Any): SystemSecurity = SystemSecurity.entries.singleOrNull { it.name == OfflineFeatureCodec.text(raw) }
        ?: OfflineFeatureCodec.reject("unsupported system security")
    fun decode(json: String): SystemSecurityDetails = with(OfflineFeatureCodec) {
        val root = parse(json); keys(root, "version", "fit_id", "revision", "is_structure", "system", "choices")
        expect(integer(root.get("version")) == 1L, "unsupported system security version")
        val revision = integer(root.get("revision")); expect(revision >= 1, "invalid security revision")
        val structure = bool(root.get("is_structure"))
        val choices = rows(root.get("choices")).map { raw ->
            val row = obj(raw); keys(row, "id", "label")
            SystemSecurityChoice(system(row.get("id")), text(row.get("label")))
        }
        expect(choices == if (structure) sourceChoices else emptyList(), "system security choices differ from source")
        SystemSecurityDetails(identity(root.get("fit_id")), revision, structure, system(root.get("system")), frozen(choices))
    }
}
