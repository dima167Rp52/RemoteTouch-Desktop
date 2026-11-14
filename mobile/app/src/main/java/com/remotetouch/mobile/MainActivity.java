package com.remotetouch.mobile;

import android.app.Activity;
import android.os.Bundle;
import android.graphics.Color;
import android.graphics.Typeface;
import android.view.View;
import android.view.Gravity;
import android.view.inputmethod.InputMethodManager;
import android.content.Context;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.webkit.WebChromeClient;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceError;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;
import android.net.Uri;

import java.util.Locale;

public class MainActivity extends Activity {
    private static final int BG = Color.rgb(8, 13, 24);
    private static final int PANEL = Color.rgb(20, 31, 52);
    private static final int BLUE = Color.rgb(37, 99, 235);
    private static final int TEXT = Color.rgb(237, 244, 255);
    private static final int MUTED = Color.rgb(145, 164, 194);

    private LinearLayout root;
    private EditText addressInput;
    private TextView status;
    private WebView webView;
    private View homeView;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().setStatusBarColor(BG);
        getWindow().setNavigationBarColor(BG);
        showHome();
    }

    private TextView text(String value, int size, int color, boolean bold) {
        TextView view = new TextView(this);
        view.setText(value);
        view.setTextSize(size);
        view.setTextColor(color);
        if (bold) view.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        return view;
    }

    private Button button(String label) {
        Button b = new Button(this);
        b.setText(label);
        b.setAllCaps(false);
        b.setTextColor(Color.WHITE);
        b.setTextSize(15);
        b.setBackgroundTintList(android.content.res.ColorStateList.valueOf(BLUE));
        return b;
    }

    private LinearLayout column() {
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setPadding(24, 22, 24, 22);
        box.setBackgroundColor(PANEL);
        return box;
    }

    private void showHome() {
        if (webView != null) {
            webView.stopLoading();
            webView.destroy();
            webView = null;
        }

        root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setGravity(Gravity.CENTER_HORIZONTAL);
        root.setPadding(22, 34, 22, 24);
        root.setBackgroundColor(BG);

        TextView brand = text("RemoteTouch", 30, TEXT, true);
        brand.setGravity(Gravity.CENTER);
        root.addView(brand);

        TextView subtitle = text("УПРАВЛЕНИЕ КОМПЬЮТЕРОМ С ТЕЛЕФОНА", 11, MUTED, true);
        subtitle.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams subParams = new LinearLayout.LayoutParams(-1, -2);
        subParams.setMargins(0, 8, 0, 28);
        root.addView(subtitle, subParams);

        LinearLayout card = column();
        TextView title = text("Добавить компьютер", 21, TEXT, true);
        card.addView(title);

        TextView hint = text("Вставь ссылку подключения из RemoteTouch Desktop. Подойдёт локальная ссылка Wi-Fi или защищённая ссылка для интернета.", 14, MUTED, false);
        hint.setPadding(0, 12, 0, 16);
        card.addView(hint);

        addressInput = new EditText(this);
        addressInput.setSingleLine(true);
        addressInput.setTextSize(14);
        addressInput.setTextColor(TEXT);
        addressInput.setHintTextColor(MUTED);
        addressInput.setHint("http://192.168.1.100:8765/?pin=...");
        addressInput.setPadding(14, 14, 14, 14);
        addressInput.setBackgroundTintList(android.content.res.ColorStateList.valueOf(Color.rgb(96, 165, 250)));
        card.addView(addressInput, new LinearLayout.LayoutParams(-1, -2));

        Button paste = button("Вставить ссылку");
        paste.setBackgroundTintList(android.content.res.ColorStateList.valueOf(Color.rgb(51, 65, 85)));
        LinearLayout.LayoutParams pasteParams = new LinearLayout.LayoutParams(-1, -2);
        pasteParams.setMargins(0, 12, 0, 4);
        card.addView(paste, pasteParams);
        paste.setOnClickListener(v -> pasteLink());

        Button connect = button("Подключить компьютер");
        LinearLayout.LayoutParams connectParams = new LinearLayout.LayoutParams(-1, -2);
        connectParams.setMargins(0, 12, 0, 0);
        card.addView(connect, connectParams);
        connect.setOnClickListener(v -> connect());

        status = text("Новый компьютер попросит подтверждение на Windows.", 12, MUTED, false);
        status.setPadding(2, 16, 2, 0);
        card.addView(status);

        LinearLayout.LayoutParams cardParams = new LinearLayout.LayoutParams(-1, -2);
        root.addView(card, cardParams);

        TextView footer = text("RemoteTouch Mobile 1.0.0", 12, MUTED, false);
        footer.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams footerParams = new LinearLayout.LayoutParams(-1, -2);
        footerParams.setMargins(0, 24, 0, 0);
        root.addView(footer, footerParams);

        homeView = root;
        setContentView(root);
    }

    private void pasteLink() {
        ClipboardManager clipboard = (ClipboardManager) getSystemService(Context.CLIPBOARD_SERVICE);
        if (clipboard != null && clipboard.hasPrimaryClip()) {
            ClipData clip = clipboard.getPrimaryClip();
            if (clip != null && clip.getItemCount() > 0) {
                CharSequence value = clip.getItemAt(0).coerceToText(this);
                addressInput.setText(value);
                addressInput.setSelection(addressInput.length());
            }
        } else {
            Toast.makeText(this, "Буфер обмена пуст", Toast.LENGTH_SHORT).show();
        }
    }

    private void connect() {
        String raw = addressInput.getText().toString().trim();
        if (raw.isEmpty()) {
            addressInput.setError("Вставь ссылку подключения");
            return;
        }

        Uri uri = Uri.parse(raw);
        String scheme = uri.getScheme();
        if (scheme == null || !(scheme.equalsIgnoreCase("http") || scheme.equalsIgnoreCase("https")) || uri.getHost() == null) {
            addressInput.setError("Нужна полная ссылка http:// или https://");
            return;
        }
        if (!uri.getQueryParameterNames().contains("pin") || uri.getQueryParameter("pin") == null || uri.getQueryParameter("pin").isEmpty()) {
            addressInput.setError("В ссылке не найден PIN. Скопируй ссылку из окна RemoteTouch Desktop.");
            return;
        }

        ((InputMethodManager) getSystemService(INPUT_METHOD_SERVICE))
                .hideSoftInputFromWindow(addressInput.getWindowToken(), 0);

        showBrowser(raw);
    }

    private void showBrowser(String url) {
        root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(BG);

        LinearLayout top = new LinearLayout(this);
        top.setGravity(Gravity.CENTER_VERTICAL);
        top.setPadding(12, 6, 12, 6);
        top.setBackgroundColor(PANEL);

        Button back = button("←");
        back.setMinWidth(52);
        back.setOnClickListener(v -> showHome());
        top.addView(back);

        TextView heading = text("RemoteTouch", 17, TEXT, true);
        heading.setPadding(12, 0, 0, 0);
        top.addView(heading, new LinearLayout.LayoutParams(0, -2, 1));

        root.addView(top, new LinearLayout.LayoutParams(-1, -2));

        webView = new WebView(this);
        webView.setBackgroundColor(BG);
        webView.getSettings().setJavaScriptEnabled(true);
        webView.getSettings().setDomStorageEnabled(true);
        webView.getSettings().setMediaPlaybackRequiresUserGesture(false);
        webView.setWebChromeClient(new WebChromeClient());
        webView.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                String scheme = request.getUrl().getScheme();
                return !(scheme.equals("http") || scheme.equals("https"));
            }

            @Override
            public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                if (request.isForMainFrame()) {
                    Toast.makeText(MainActivity.this, "Не удалось подключиться. Проверь сервер и ссылку.", Toast.LENGTH_LONG).show();
                }
            }
        });
        root.addView(webView, new LinearLayout.LayoutParams(-1, 0, 1));
        setContentView(root);
        webView.loadUrl(url);
    }

    @Override
    public void onBackPressed() {
        if (webView != null && webView.canGoBack()) {
            webView.goBack();
        } else if (webView != null) {
            showHome();
        } else {
            super.onBackPressed();
        }
    }

    @Override
    protected void onDestroy() {
        if (webView != null) {
            webView.stopLoading();
            webView.destroy();
            webView = null;
        }
        super.onDestroy();
    }
}
