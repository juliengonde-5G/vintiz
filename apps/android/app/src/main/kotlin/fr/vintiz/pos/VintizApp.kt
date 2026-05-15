package fr.vintiz.pos

import android.app.Application
import timber.log.Timber

class VintizApp : Application() {
    override fun onCreate() {
        super.onCreate()
        if (BuildConfig.DEBUG) {
            Timber.plant(Timber.DebugTree())
        }
    }
}
