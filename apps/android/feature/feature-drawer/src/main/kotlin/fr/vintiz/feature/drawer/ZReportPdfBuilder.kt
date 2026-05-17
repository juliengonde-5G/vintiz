package fr.vintiz.feature.drawer

import android.content.Context
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Typeface
import android.graphics.pdf.PdfDocument
import androidx.core.content.FileProvider
import fr.vintiz.core.common.Money
import fr.vintiz.data.reports.ZReportDto
import java.io.File
import java.io.FileOutputStream

/**
 * Génère un PDF du Z-Report (rapport de fermeture de caisse) côté
 * Android. Le PDF reproduit visuellement le ticket Z mais en A4 :
 * en-tête Vintiz + ouverture/fermeture + totaux par méthode + écart.
 *
 * Le résultat est sauvegardé dans `cacheDir/vintiz-zreport-<ts>.pdf`
 * et retourné comme URI FileProvider partageable via Intent ACTION_SEND.
 */
object ZReportPdfBuilder {

    fun build(context: Context, z: ZReportDto): android.net.Uri {
        val doc = PdfDocument()
        // A4 portrait à 72 DPI : 595 × 842 points
        val pageInfo = PdfDocument.PageInfo.Builder(595, 842, 1).create()
        val page = doc.startPage(pageInfo)
        val canvas = page.canvas

        val tealPaint = Paint().apply {
            color = Color.parseColor("#0B7A6A")
            isAntiAlias = true
        }
        val inkPaint = Paint().apply {
            color = Color.parseColor("#0E0E0C")
            isAntiAlias = true
        }
        val mutePaint = Paint().apply {
            color = Color.parseColor("#8B8B86")
            isAntiAlias = true
        }

        var y = 60f
        // Header
        canvas.drawText(
            "VINTIZ — Z-Report",
            48f, y,
            Paint(tealPaint).apply {
                textSize = 24f
                typeface = Typeface.create(Typeface.SERIF, Typeface.BOLD)
            },
        )
        y += 28f
        canvas.drawText(
            "Drawer : ${z.drawer_id.take(8)}",
            48f, y,
            Paint(mutePaint).apply { textSize = 10f },
        )
        y += 36f

        // Dates
        canvas.drawText("Ouverture", 48f, y, Paint(mutePaint).apply { textSize = 10f })
        canvas.drawText(z.opened_at.take(16).replace("T", " "), 200f, y,
            Paint(inkPaint).apply { textSize = 12f })
        y += 18f
        canvas.drawText("Fermeture", 48f, y, Paint(mutePaint).apply { textSize = 10f })
        canvas.drawText(z.closed_at.take(16).replace("T", " "), 200f, y,
            Paint(inkPaint).apply { textSize = 12f })
        y += 32f

        // Cash flow
        row(canvas, "Fond initial",
            Money(z.opening_amount_cents).format(), y, inkPaint, mutePaint)
        y += 22f
        row(canvas, "Total espèces",
            Money(z.total_cash_cents).format(), y, inkPaint, mutePaint)
        y += 22f
        row(canvas, "Attendu (caisse)",
            Money(z.expected_cents).format(), y, inkPaint, mutePaint)
        y += 22f
        row(canvas, "Compté (caisse)",
            Money(z.closing_amount_cents).format(), y, inkPaint, mutePaint)
        y += 22f
        val diff = z.diff_cents
        val diffColor = when {
            diff == 0L -> "#0B7A6A"
            diff > 0L -> "#0E0E0C"
            else -> "#E84E8B"
        }
        row(
            canvas, "Écart caisse",
            Money(diff).format(),
            y, inkPaint, mutePaint,
            rightColor = Color.parseColor(diffColor),
        )
        y += 36f

        // Totals by method
        canvas.drawText("Par méthode", 48f, y,
            Paint(tealPaint).apply {
                textSize = 14f
                typeface = Typeface.create(Typeface.SERIF, Typeface.BOLD)
            })
        y += 22f
        row(canvas, "Espèces", Money(z.total_cash_cents).format(), y, inkPaint, mutePaint)
        y += 18f
        row(canvas, "CB SumUp", Money(z.total_card_cents).format(), y, inkPaint, mutePaint)
        y += 18f
        row(canvas, "Chèque", Money(z.total_cheque_cents).format(), y, inkPaint, mutePaint)
        y += 36f

        // Footer
        canvas.drawText(
            "Vintiz Vernon — Boutique seconde main premium",
            48f, 800f,
            Paint(mutePaint).apply { textSize = 9f },
        )

        doc.finishPage(page)

        val ts = System.currentTimeMillis()
        val outFile = File(context.cacheDir, "vintiz-zreport-$ts.pdf")
        FileOutputStream(outFile).use { doc.writeTo(it) }
        doc.close()

        return FileProvider.getUriForFile(
            context,
            "${context.packageName}.fileprovider",
            outFile,
        )
    }

    private fun row(
        canvas: android.graphics.Canvas,
        label: String,
        value: String,
        y: Float,
        leftPaint: Paint,
        labelPaint: Paint,
        rightColor: Int = leftPaint.color,
    ) {
        canvas.drawText(label, 48f, y, Paint(labelPaint).apply { textSize = 11f })
        val rightPaint = Paint(leftPaint).apply {
            textSize = 13f
            typeface = Typeface.MONOSPACE
            textAlign = Paint.Align.RIGHT
            color = rightColor
        }
        canvas.drawText(value, 547f, y, rightPaint)
    }
}
