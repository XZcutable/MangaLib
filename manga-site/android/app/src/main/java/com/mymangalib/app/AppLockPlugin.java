package com.mymangalib.app;

import android.view.WindowManager;

import androidx.annotation.NonNull;
import androidx.biometric.BiometricManager;
import androidx.biometric.BiometricPrompt;
import androidx.core.content.ContextCompat;
import androidx.fragment.app.FragmentActivity;

import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

/**
 * App lock: asks for the phone's own unlock (face, fingerprint, or the screen-lock PIN/pattern).
 * It only guards the screen, so no keys are tied to it. The lock screen itself is drawn by the web app.
 */
@CapacitorPlugin(name = "AppLock")
public class AppLockPlugin extends Plugin {

    // Weak biometrics too, or Samsung's face unlock wouldn't count
    private static final int AUTHENTICATORS =
        BiometricManager.Authenticators.BIOMETRIC_WEAK | BiometricManager.Authenticators.DEVICE_CREDENTIAL;

    /** Whether the phone has any screen lock this app can ask for. */
    @PluginMethod
    public void availability(PluginCall call) {
        int status = BiometricManager.from(getContext()).canAuthenticate(AUTHENTICATORS);
        JSObject result = new JSObject();
        result.put("available", status == BiometricManager.BIOMETRIC_SUCCESS);
        String reason = null;
        if (status == BiometricManager.BIOMETRIC_ERROR_NONE_ENROLLED) reason = "none_enrolled";
        else if (status == BiometricManager.BIOMETRIC_ERROR_NO_HARDWARE) reason = "no_hardware";
        else if (status != BiometricManager.BIOMETRIC_SUCCESS) reason = "unavailable";
        result.put("reason", reason);
        call.resolve(result);
    }

    /** Shows Android's unlock prompt. Resolves when the user unlocks; rejects with canceled/lockout/unavailable. */
    @PluginMethod
    public void authenticate(PluginCall call) {
        String title = call.getString("title", "Unlock");
        String subtitle = call.getString("subtitle");
        getActivity().runOnUiThread(() -> {
            FragmentActivity activity = getActivity();
            BiometricPrompt prompt = new BiometricPrompt(
                activity,
                ContextCompat.getMainExecutor(activity),
                new BiometricPrompt.AuthenticationCallback() {
                    @Override
                    public void onAuthenticationSucceeded(@NonNull BiometricPrompt.AuthenticationResult result) {
                        call.resolve();
                    }

                    @Override
                    public void onAuthenticationError(int code, @NonNull CharSequence message) {
                        String reason;
                        switch (code) {
                            case BiometricPrompt.ERROR_LOCKOUT:
                            case BiometricPrompt.ERROR_LOCKOUT_PERMANENT:
                                reason = "lockout";
                                break;
                            case BiometricPrompt.ERROR_HW_NOT_PRESENT:
                            case BiometricPrompt.ERROR_HW_UNAVAILABLE:
                            case BiometricPrompt.ERROR_NO_BIOMETRICS:
                            case BiometricPrompt.ERROR_NO_DEVICE_CREDENTIAL:
                                reason = "unavailable";
                                break;
                            default:
                                reason = "canceled";
                        }
                        call.reject(message.toString(), reason);
                    }

                    // A face or finger that didn't match: the prompt stays up and lets the user try again
                }
            );
            BiometricPrompt.PromptInfo.Builder info = new BiometricPrompt.PromptInfo.Builder()
                .setTitle(title)
                .setAllowedAuthenticators(AUTHENTICATORS);
            if (subtitle != null) info.setSubtitle(subtitle);
            try {
                prompt.authenticate(info.build());
            } catch (Exception error) {
                call.reject(error.getMessage(), "unavailable");
            }
        });
    }

    /** FLAG_SECURE: blanks the app in the recent-apps view. Android also blocks screenshots with it. */
    @PluginMethod
    public void setSecure(PluginCall call) {
        boolean on = Boolean.TRUE.equals(call.getBoolean("on", false));
        getActivity().runOnUiThread(() -> {
            if (on) getActivity().getWindow().addFlags(WindowManager.LayoutParams.FLAG_SECURE);
            else getActivity().getWindow().clearFlags(WindowManager.LayoutParams.FLAG_SECURE);
            call.resolve();
        });
    }
}
