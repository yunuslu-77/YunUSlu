package dev.yai.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.Chat
import androidx.compose.material.icons.automirrored.rounded.EventNote
import androidx.compose.material.icons.rounded.Home
import androidx.compose.material.icons.rounded.Psychology
import androidx.compose.material.icons.rounded.School
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.core.splashscreen.SplashScreen.Companion.installSplashScreen
import dev.yai.app.core.Alarms
import dev.yai.app.ui.MainViewModel
import dev.yai.app.ui.screens.BrainScreen
import dev.yai.app.ui.screens.ChatScreen
import dev.yai.app.ui.screens.HomeScreen
import dev.yai.app.ui.screens.LearnScreen
import dev.yai.app.ui.screens.RUNTIME_PERMISSIONS
import dev.yai.app.ui.screens.SettingsScreen
import dev.yai.app.ui.screens.TasksScreen
import dev.yai.app.ui.screens.WelcomeScreen
import dev.yai.app.ui.theme.Brand
import dev.yai.app.ui.theme.YaiTheme

class MainActivity : ComponentActivity() {
    private val vm: MainViewModel by viewModels()
    private val permissions = registerForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { }

    override fun onCreate(savedInstanceState: Bundle?) {
        installSplashScreen()
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        (vm.yai.alarms as? Alarms)?.rearmAll()

        setContent {
            YaiTheme {
                var onboarded by remember { mutableStateOf(vm.prefs.onboarded) }
                if (!onboarded) {
                    WelcomeScreen(testKey = { vm.saveAndTestKey(it) }) {
                        vm.prefs.onboarded = true
                        onboarded = true
                        permissions.launch(RUNTIME_PERMISSIONS)
                    }
                    return@YaiTheme
                }
                App(vm)
            }
        }
    }

    override fun onResume() {
        super.onResume()
        vm.refreshAll()
    }
}

private data class Tab(val label: String, val icon: androidx.compose.ui.graphics.vector.ImageVector)

private val TABS = listOf(Tab("Ana Sayfa", Icons.Rounded.Home), Tab("Sohbet", Icons.AutoMirrored.Rounded.Chat),
    Tab("Görevler", Icons.AutoMirrored.Rounded.EventNote), Tab("Öğren", Icons.Rounded.School), Tab("Beyin", Icons.Rounded.Psychology))

@androidx.compose.runtime.Composable
private fun App(vm: MainViewModel) {
    var tab by rememberSaveable { mutableIntStateOf(0) }
    var settings by rememberSaveable { mutableStateOf(false) }
    var prefill by remember { mutableStateOf<String?>(null) }
    val error by vm.error.collectAsState()
    val snack = remember { SnackbarHostState() }
    LaunchedEffect(error) { error?.let { snack.showSnackbar(it); vm.clearError() } }

    if (settings) {
        BackHandler { settings = false }
        Box(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background)) {
            SettingsScreen(vm) { settings = false }
        }
        return
    }
    BackHandler(enabled = tab != 0) { tab = 0 }
    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
        snackbarHost = { SnackbarHost(snack) },
        bottomBar = {
            NavigationBar(containerColor = MaterialTheme.colorScheme.surface) {
                TABS.forEachIndexed { i, t ->
                    NavigationBarItem(selected = tab == i, onClick = { tab = i },
                        icon = { Icon(t.icon, t.label) }, label = { Text(t.label) },
                        colors = NavigationBarItemDefaults.colors(selectedIconColor = Brand.Violet, selectedTextColor = Brand.Violet,
                            indicatorColor = MaterialTheme.colorScheme.primaryContainer))
                }
            }
        },
        contentWindowInsets = androidx.compose.foundation.layout.WindowInsets(0),
    ) { pad ->
        Box(Modifier.padding(pad).fillMaxSize()) {
            when (tab) {
                0 -> HomeScreen(vm, openSettings = { settings = true }, openChatWith = { prefill = it; tab = 1 })
                1 -> ChatScreen(vm, prefill) { prefill = null }
                2 -> TasksScreen(vm)
                3 -> LearnScreen()
                else -> BrainScreen(vm)
            }
        }
    }
}
