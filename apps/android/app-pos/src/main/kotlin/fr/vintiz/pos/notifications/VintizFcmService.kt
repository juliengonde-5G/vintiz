package fr.vintiz.pos.notifications

import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import dagger.hilt.android.AndroidEntryPoint
import fr.vintiz.data.notifications.NotificationsRepository
import fr.vintiz.pos.R
import javax.inject.Inject
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import timber.log.Timber

/**
 * Reçoit les push FCM (vente importante, dépôt, alerte stock — émises
 * par les jobs cron côté backend). À l'arrivée d'un nouveau token, le
 * service appelle [NotificationsRepository.register] pour le faire
 * connaître au backend.
 *
 * Sans google-services.json (cas dev local), Firebase n'instancie pas
 * le service et les méthodes ne sont jamais appelées — l'app continue
 * de fonctionner sans push.
 */
@AndroidEntryPoint
class VintizFcmService : FirebaseMessagingService() {

    @Inject lateinit var repository: NotificationsRepository

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    override fun onNewToken(token: String) {
        Timber.i("FCM token received (len=%d)", token.length)
        scope.launch { repository.register(token) }
    }

    override fun onMessageReceived(message: RemoteMessage) {
        val title = message.notification?.title ?: message.data["title"] ?: return
        val body = message.notification?.body ?: message.data["body"].orEmpty()
        showNotification(title, body)
    }

    private fun showNotification(title: String, body: String) {
        val builder = NotificationCompat.Builder(this, fr.vintiz.pos.VintizApp.CHANNEL_ID)
            .setSmallIcon(R.mipmap.ic_launcher)
            .setContentTitle(title)
            .setContentText(body)
            .setAutoCancel(true)
        if (ContextCompat.checkSelfPermission(
                this,
                android.Manifest.permission.POST_NOTIFICATIONS,
            ) == android.content.pm.PackageManager.PERMISSION_GRANTED
        ) {
            NotificationManagerCompat.from(this)
                .notify(System.currentTimeMillis().toInt(), builder.build())
        }
    }
}
