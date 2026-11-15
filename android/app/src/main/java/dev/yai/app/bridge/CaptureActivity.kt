package dev.yai.app.bridge

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageCapture
import androidx.camera.core.ImageCaptureException
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.core.content.ContextCompat
import kotlinx.coroutines.CompletableDeferred
import java.io.File

/** Görünmez etkinlik: kamerayla tek fotoğraf çeker ve kapanır. */
class CaptureActivity : ComponentActivity() {
    companion object {
        @Volatile var pending: CompletableDeferred<ByteArray>? = null
        const val EXTRA_FRONT = "front"
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val result = pending
        val front = intent.getBooleanExtra(EXTRA_FRONT, false)
        val providerFuture = ProcessCameraProvider.getInstance(this)
        providerFuture.addListener({
            try {
                val provider = providerFuture.get()
                val capture = ImageCapture.Builder().setCaptureMode(ImageCapture.CAPTURE_MODE_MINIMIZE_LATENCY).build()
                val selector = if (front) CameraSelector.DEFAULT_FRONT_CAMERA else CameraSelector.DEFAULT_BACK_CAMERA
                provider.unbindAll()
                provider.bindToLifecycle(this, selector, capture)
                val file = File(cacheDir, "yai_photo.jpg")
                capture.takePicture(ImageCapture.OutputFileOptions.Builder(file).build(), ContextCompat.getMainExecutor(this),
                    object : ImageCapture.OnImageSavedCallback {
                        override fun onImageSaved(o: ImageCapture.OutputFileResults) {
                            result?.complete(file.readBytes()); file.delete(); provider.unbindAll(); finish()
                        }
                        override fun onError(e: ImageCaptureException) {
                            result?.completeExceptionally(e); provider.unbindAll(); finish()
                        }
                    })
            } catch (e: Exception) {
                result?.completeExceptionally(e); finish()
            }
        }, ContextCompat.getMainExecutor(this))
    }
}
