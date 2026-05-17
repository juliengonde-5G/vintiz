package fr.vintiz.hardware.api

/**
 * Garde-fou de défense en profondeur : avant d'ouvrir un socket TCP
 * vers une imprimante, on s'assure que le host fourni par l'API
 * `hardware.json` est bien une cible LAN (RFC 1918, loopback, ou
 * mDNS .local). Si l'API hardware était compromise, on évite qu'un
 * attaquant fasse parler la tablette à une IP arbitraire d'internet.
 *
 * Accepté :
 * - 10.x.x.x (RFC 1918 — VLAN boutique typique)
 * - 172.16.x.x à 172.31.x.x (RFC 1918)
 * - 192.168.x.x (RFC 1918 — Box typique)
 * - 127.x.x.x (loopback)
 * - 169.254.x.x (link-local IPv4 — auto-config)
 * - *.local (mDNS Bonjour)
 *
 * Refusé : IPs publiques, IPv6 (l'imprimante boutique est IPv4),
 * domaines internet (vintiz.fr…), URLs.
 */
fun String.isPrivateLanTarget(): Boolean {
    val host = trim().lowercase()
    if (host.isEmpty()) return false
    if (host.endsWith(".local")) return true
    val ipv4 = Regex("""^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$""")
    val match = ipv4.matchEntire(host) ?: return false
    val (a, b, _, _) = match.destructured
    val o1 = a.toIntOrNull() ?: return false
    val o2 = b.toIntOrNull() ?: return false
    if (o1 !in 0..255 || o2 !in 0..255) return false
    return when {
        o1 == 10 -> true
        o1 == 127 -> true
        o1 == 172 && o2 in 16..31 -> true
        o1 == 192 && o2 == 168 -> true
        o1 == 169 && o2 == 254 -> true
        else -> false
    }
}
