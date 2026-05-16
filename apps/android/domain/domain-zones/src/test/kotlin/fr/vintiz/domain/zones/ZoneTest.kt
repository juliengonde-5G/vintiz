package fr.vintiz.domain.zones

import com.google.common.truth.Truth.assertThat
import org.junit.jupiter.api.Test

class ZoneTest {

    private fun zone(occ: Double?) = Zone(
        id = "z1",
        name = "Petits prix",
        description = null,
        capacity = 50,
        productTypes = emptyList(),
        colorHex = "#CDE5DF",
        icon = null,
        isWindow = false,
        posX = 0, posY = 0, width = 120, height = 80,
        shape = ZoneShape.Rectangle,
        nProducts = 38,
        occupancyPct = occ,
        avgScore = 6.5,
        scoreBucket = ScoreBucket.Good,
    )

    @Test
    fun `saturated des 95 pourcent`() {
        assertThat(zone(94.9).isSaturated).isFalse()
        assertThat(zone(95.0).isSaturated).isTrue()
        assertThat(zone(120.0).isSaturated).isTrue()
    }

    @Test
    fun `underused en dessous de 50 pourcent`() {
        assertThat(zone(50.0).isUnderused).isFalse()
        assertThat(zone(49.9).isUnderused).isTrue()
        assertThat(zone(0.0).isUnderused).isTrue()
    }

    @Test
    fun `occupancyRatio cape a 1`() {
        assertThat(zone(80.0).occupancyRatio).isEqualTo(0.8f)
        assertThat(zone(120.0).occupancyRatio).isEqualTo(1f)
    }

    @Test
    fun `occupancyRatio zero si pct null`() {
        assertThat(zone(null).occupancyRatio).isEqualTo(0f)
        assertThat(zone(null).isSaturated).isFalse()
        assertThat(zone(null).isUnderused).isFalse()
    }

    @Test
    fun `score bucket decode fallback Unknown`() {
        assertThat(ScoreBucket.fromKey("excellent")).isEqualTo(ScoreBucket.Excellent)
        assertThat(ScoreBucket.fromKey("GOOD")).isEqualTo(ScoreBucket.Good)
        assertThat(ScoreBucket.fromKey(null)).isEqualTo(ScoreBucket.Unknown)
        assertThat(ScoreBucket.fromKey("zzz")).isEqualTo(ScoreBucket.Unknown)
    }

    @Test
    fun `shape decode fallback Rectangle`() {
        assertThat(ZoneShape.fromKey("square")).isEqualTo(ZoneShape.Square)
        assertThat(ZoneShape.fromKey("l-shape")).isEqualTo(ZoneShape.LShape)
        assertThat(ZoneShape.fromKey(null)).isEqualTo(ZoneShape.Rectangle)
        assertThat(ZoneShape.fromKey("inexistant")).isEqualTo(ZoneShape.Rectangle)
    }
}
