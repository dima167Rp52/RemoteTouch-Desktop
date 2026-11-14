package com.remotetouch.mobile;

import android.app.Activity;
import android.os.Bundle;
import android.graphics.Color;
import android.graphics.Typeface;
import android.view.View;
import android.view.Gravity;
import android.view.inputmethod.InputMethodManager;
import android.content.Context;
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

import org.json.JSONObject;

import java.net.DatagramPacket;
import java.net.DatagramSocket;
import java.net.InetSocketAddress;
import java.net.SocketTimeoutException;
import java.net.HttpURLConnection;
import java.net.URL;
import java.io.OutputStream;
import java.io.ByteArrayOutputStream;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.nio.charset.StandardCharsets;
import java.util.LinkedHashMap;
import java.util.Locale;
import java.util.Map;

public class MainActivity extends Activity {
    private static final int BG = Color.rgb(8, 13, 24);
    private static final int PANEL = Color.rgb(20, 31, 52);
    private static final int BLUE = Color.rgb(37, 99, 235);
    private static final int TEXT = Color.rgb(237, 244, 255);
    private static final int MUTED = Color.rgb(145, 164, 194);
    private static final int DISCOVERY_PORT = 8766;

    private LinearLayout root;
    private LinearLayout deviceList;
    private TextView status;
    private EditText addressInput;
    private EditText codeInput;
    private final ExecutorService network = Executors.newSingleThreadExecutor();
    private WebView webView;
    private String allowedHost = "";
    private String allowedScheme = "";
    private int allowedPort = -1;
    private String connectedBaseUrl = "";
    private String sessionToken = "";
    private boolean allowRemotePage = false;
    private final Map<String, String> devices = new LinkedHashMap<>();
    private volatile boolean scanning = false;
    private volatile DatagramSocket discoverySocket;
    private Thread discoveryThread;

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
        b.setTextSize(14);
        b.setBackgroundTintList(android.content.res.ColorStateList.valueOf(BLUE));
        return b;
    }

    private LinearLayout column() {
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setPadding(20, 18, 20, 18);
        box.setBackgroundColor(PANEL);
        return box;
    }

    private void showHome() {
        stopDiscovery();
        if (webView != null) {
            webView.stopLoading();
            webView.destroy();
            webView = null;
        }

        root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(20, 28, 20, 20);
        root.setBackgroundColor(BG);

        TextView brand = text("RemoteTouch", 30, TEXT, true);
        brand.setGravity(Gravity.CENTER);
        root.addView(brand);

        TextView subtitle = text("ВЫБЕРИ КОМПЬЮТЕР ДЛЯ ПОДКЛЮЧЕНИЯ", 11, MUTED, true);
        subtitle.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams sub = new LinearLayout.LayoutParams(-1, -2);
        sub.setMargins(0, 7, 0, 22);
        root.addView(subtitle, sub);

        LinearLayout card = column();
        LinearLayout titleRow = new LinearLayout(this);
        titleRow.setGravity(Gravity.CENTER_VERTICAL);
        TextView title = text("Компьютеры рядом", 20, TEXT, true);
        titleRow.addView(title, new LinearLayout.LayoutParams(0, -2, 1));
        Button refresh = button("↻");
        refresh.setMinWidth(52);
        titleRow.addView(refresh);
        card.addView(titleRow);
        refresh.setOnClickListener(v -> startDiscovery());

        status = text("Ищем компьютеры в этой Wi-Fi сети…", 13, MUTED, false);
        status.setPadding(0, 8, 0, 12);
        card.addView(status);

        deviceList = new LinearLayout(this);
        deviceList.setOrientation(LinearLayout.VERTICAL);
        card.addView(deviceList);
        root.addView(card);

        LinearLayout codeCard = column();
        TextView codeTitle = text("Подключение через интернет", 18, TEXT, true);
        codeCard.addView(codeTitle);
        TextView codeHint = text("Введи код из 4 случайных букв и цифр, который показан в RemoteTouch на компьютере.", 12, MUTED, false);
        codeHint.setPadding(0, 6, 0, 10);
        codeCard.addView(codeHint);
        codeInput = new EditText(this);
        codeInput.setSingleLine(true);
        codeInput.setTextSize(22);
        codeInput.setTextColor(TEXT);
        codeInput.setHintTextColor(MUTED);
        codeInput.setHint("Например, K7M2");
        codeInput.setLetterSpacing(0.18f);
        codeInput.setInputType(android.text.InputType.TYPE_CLASS_TEXT | android.text.InputType.TYPE_TEXT_FLAG_CAP_CHARACTERS);
        codeInput.setFilters(new android.text.InputFilter[]{new android.text.InputFilter.LengthFilter(4)});
        codeInput.setBackgroundTintList(android.content.res.ColorStateList.valueOf(Color.rgb(96, 165, 250)));
        codeCard.addView(codeInput, new LinearLayout.LayoutParams(-1, -2));
        Button codeConnect = button("Подключиться к компьютеру");
        LinearLayout.LayoutParams ccp = new LinearLayout.LayoutParams(-1, -2);
        ccp.setMargins(0, 10, 0, 0);
        codeCard.addView(codeConnect, ccp);
        codeConnect.setOnClickListener(v -> connectByCode());
        LinearLayout.LayoutParams cdp = new LinearLayout.LayoutParams(-1, -2);
        cdp.setMargins(0, 0, 0, 14);
        root.addView(codeCard, cdp);

        LinearLayout manual = column();
        TextView manualTitle = text("Ручное подключение (резервный способ)", 16, TEXT, true);
        manual.addView(manualTitle);
        TextView hint = text("Можно вручную вставить ссылку компьютера, если подключаешься через интернет.", 12, MUTED, false);
        hint.setPadding(0, 6, 0, 10);
        manual.addView(hint);

        addressInput = new EditText(this);
        addressInput.setSingleLine(true);
        addressInput.setTextSize(14);
        addressInput.setTextColor(TEXT);
        addressInput.setHintTextColor(MUTED);
        addressInput.setHint("https://имя-компьютера.ts.net/?pin=…");
        addressInput.setPadding(12, 12, 12, 12);
        addressInput.setBackgroundTintList(android.content.res.ColorStateList.valueOf(Color.rgb(96, 165, 250)));
        manual.addView(addressInput, new LinearLayout.LayoutParams(-1, -2));

        Button connect = button("Подключиться по ссылке");
        LinearLayout.LayoutParams cp = new LinearLayout.LayoutParams(-1, -2);
        cp.setMargins(0, 10, 0, 0);
        manual.addView(connect, cp);
        connect.setOnClickListener(v -> connectManual());
        LinearLayout.LayoutParams mp = new LinearLayout.LayoutParams(-1, -2);
        mp.setMargins(0, 14, 0, 0);
        root.addView(manual, mp);

        TextView footer = text("RemoteTouch Mobile 1.1.0", 11, MUTED, false);
        footer.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams fp = new LinearLayout.LayoutParams(-1, -2);
        fp.setMargins(0, 18, 0, 0);
        root.addView(footer, fp);

        setContentView(root);
        renderDevices();
        startDiscovery();
    }

    private void renderDevices() {
        if (deviceList == null) return;
        deviceList.removeAllViews();
        if (devices.isEmpty()) {
            TextView empty = text("Пока компьютеры не найдены. Убедись, что RemoteTouch Desktop запущен и телефон подключён к той же Wi-Fi сети.", 13, MUTED, false);
            empty.setPadding(0, 8, 0, 4);
            empty.setLineSpacing(3, 1.0f);
            deviceList.addView(empty);
            return;
        }
        for (Map.Entry<String, String> entry : devices.entrySet()) {
            LinearLayout row = new LinearLayout(this);
            row.setGravity(Gravity.CENTER_VERTICAL);
            row.setPadding(12, 10, 8, 10);
            row.setBackgroundColor(Color.rgb(11, 21, 39));
            LinearLayout info = new LinearLayout(this);
            info.setOrientation(LinearLayout.VERTICAL);
            TextView name = text(entry.getKey(), 15, TEXT, true);
            TextView online = text("● В сети • локальная Wi-Fi", 11, Color.rgb(134, 239, 172), false);
            info.addView(name);
            info.addView(online);
            row.addView(info, new LinearLayout.LayoutParams(0, -2, 1));
            Button choose = button("Выбрать");
            row.addView(choose);
            String url = entry.getValue();
            choose.setOnClickListener(v -> showBrowser(url));
            LinearLayout.LayoutParams rp = new LinearLayout.LayoutParams(-1, -2);
            rp.setMargins(0, 0, 0, 8);
            deviceList.addView(row, rp);
        }
    }

    private void startDiscovery() {
        stopDiscovery();
        devices.clear();
        renderDevices();
        status.setText("Ищем компьютеры в локальной сети…");
        scanning = true;
        discoveryThread = new Thread(() -> {
            long deadline = System.currentTimeMillis() + 9000;
            DatagramSocket socket = null;
            try {
                socket = new DatagramSocket(null);
                socket.setReuseAddress(true);
                socket.bind(new InetSocketAddress(DISCOVERY_PORT));
                socket.setSoTimeout(700);
                discoverySocket = socket;
                byte[] buffer = new byte[4096];
                while (scanning && System.currentTimeMillis() < deadline) {
                    DatagramPacket packet = new DatagramPacket(buffer, buffer.length);
                    try {
                        socket.receive(packet);
                        String raw = new String(packet.getData(), packet.getOffset(), packet.getLength(), StandardCharsets.UTF_8);
                        JSONObject data = new JSONObject(raw);
                        if (!"remotetouch_discovery".equals(data.optString("type"))) continue;
                        String name = data.optString("name", "Компьютер");
                        String url = data.optString("url", "");
                        Uri uri = Uri.parse(url);
                        if (uri.getHost() == null || !"http".equalsIgnoreCase(uri.getScheme())
                                || uri.getQueryParameter("pin") == null) continue;
                        runOnUiThread(() -> {
                            if (!scanning || deviceList == null) return;
                            devices.put(name, url);
                            status.setText("Найдено компьютеров: " + devices.size());
                            renderDevices();
                        });
                    } catch (SocketTimeoutException ignored) {
                    } catch (Exception ignored) {
                    }
                }
            } catch (Exception ignored) {
            } finally {
                if (socket != null) socket.close();
                discoverySocket = null;
                scanning = false;
                runOnUiThread(() -> {
                    if (status != null && webView == null) {
                        status.setText(devices.isEmpty()
                                ? "Не нашли компьютеры. Проверь одну Wi-Fi сеть и включённый сервер."
                                : "Поиск завершён. Выбери компьютер.");
                    }
                });
            }
        }, "RemoteTouch-LAN-Discovery");
        discoveryThread.setDaemon(true);
        discoveryThread.start();
    }

    private void stopDiscovery() {
        scanning = false;
        DatagramSocket socket = discoverySocket;
        if (socket != null) socket.close();
        discoverySocket = null;
    }

    private void showConnectedControls(String remoteUrl) {
        Uri uri = Uri.parse(remoteUrl);
        sessionToken = uri.getQueryParameter("token");
        connectedBaseUrl = uri.getScheme() + "://" + uri.getAuthority();
        allowRemotePage = false;
        if (webView != null) {
            webView.stopLoading();
            webView.destroy();
            webView = null;
        }
        root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(22, 30, 22, 22);
        root.setBackgroundColor(BG);
        TextView heading = text("Компьютер подключён", 24, TEXT, true);
        heading.setGravity(Gravity.CENTER);
        root.addView(heading);
        TextView sub = text("RemoteTouch Desktop • управление приложением", 13, MUTED, false);
        sub.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams sp = new LinearLayout.LayoutParams(-1, -2);
        sp.setMargins(0, 8, 0, 24);
        root.addView(sub, sp);
        Button start = button("▶ Запустить удалённое управление");
        root.addView(start);
        start.setOnClickListener(v -> sendRemoteAction("start"));
        Button stop = button("■ Остановить удалённое управление");
        LinearLayout.LayoutParams stp = new LinearLayout.LayoutParams(-1, -2);
        stp.setMargins(0, 10, 0, 0);
        root.addView(stop, stp);
        stop.setOnClickListener(v -> sendRemoteAction("stop"));
        Button stream = button("Трансляция и управление экраном");
        LinearLayout.LayoutParams tp = new LinearLayout.LayoutParams(-1, -2);
        tp.setMargins(0, 20, 0, 0);
        root.addView(stream, tp);
        stream.setOnClickListener(v -> showBrowser(remoteUrl));
        Button back = button("Отключиться");
        LinearLayout.LayoutParams bp = new LinearLayout.LayoutParams(-1, -2);
        bp.setMargins(0, 10, 0, 0);
        root.addView(back, bp);
        back.setOnClickListener(v -> showHome());
        status = text("Подключено. Компьютер ожидает команды.", 13, MUTED, false);
        status.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams statusParams = new LinearLayout.LayoutParams(-1, -2);
        statusParams.setMargins(0, 20, 0, 0);
        root.addView(status, statusParams);
        setContentView(root);
        sendRemoteAction("status");
    }

    private void sendRemoteAction(String action) {
        if (sessionToken.isEmpty() || connectedBaseUrl.isEmpty()) return;
        status.setText("Отправляем команду…");
        network.execute(() -> {
            HttpURLConnection connection = null;
            try {
                String path = action.equals("status") ? "/app/status" :
                        (action.equals("start") ? "/app/remote/start" : "/app/remote/stop");
                URL endpoint = new URL(connectedBaseUrl + path + "?token=" + Uri.encode(sessionToken));
                connection = (HttpURLConnection) endpoint.openConnection();
                connection.setRequestMethod(action.equals("status") ? "GET" : "POST");
                connection.setConnectTimeout(10000);
                connection.setReadTimeout(10000);
                if (!action.equals("status")) connection.setDoOutput(true);
                int code = connection.getResponseCode();
                java.io.InputStream input = code >= 200 && code < 300
                        ? connection.getInputStream() : connection.getErrorStream();
                ByteArrayOutputStream bytes = new ByteArrayOutputStream();
                byte[] buffer = new byte[1024];
                int count;
                while ((count = input.read(buffer)) != -1) bytes.write(buffer, 0, count);
                JSONObject result = new JSONObject(new String(bytes.toByteArray(), StandardCharsets.UTF_8));
                if (code < 200 || code >= 300) throw new Exception("Компьютер отклонил команду");
                boolean enabled = result.optBoolean("remote_enabled", false);
                String message = action.equals("status")
                        ? (enabled ? "Удалённое управление включено." : "Удалённое управление выключено.")
                        : (enabled ? "Удалённое управление включено." : "Удалённое управление выключено.");
                runOnUiThread(() -> status.setText(message));
            } catch (Exception e) {
                String message = e.getMessage() == null ? "Нет связи с компьютером" : e.getMessage();
                runOnUiThread(() -> status.setText(message));
            } finally {
                if (connection != null) connection.disconnect();
            }
        });
    }

    private void connectByCode() {
        String code = codeInput.getText().toString().trim().toUpperCase(Locale.ROOT);
        if (!code.matches("[A-Z0-9]{4}")) {
            codeInput.setError("Нужны ровно 4 буквы или цифры");
            return;
        }
        ((InputMethodManager) getSystemService(INPUT_METHOD_SERVICE))
                .hideSoftInputFromWindow(codeInput.getWindowToken(), 0);
        status.setText("Ищем компьютер по коду…");
        network.execute(() -> {
            HttpURLConnection connection = null;
            try {
                URL endpoint = new URL("https://remotetouch-directory.onrender.com/api/lookup");
                connection = (HttpURLConnection) endpoint.openConnection();
                connection.setRequestMethod("POST");
                connection.setConnectTimeout(12000);
                connection.setReadTimeout(12000);
                connection.setDoOutput(true);
                connection.setRequestProperty("Content-Type", "application/json");
                byte[] body = new JSONObject().put("code", code).toString().getBytes(StandardCharsets.UTF_8);
                try (OutputStream out = connection.getOutputStream()) { out.write(body); }
                int statusCode = connection.getResponseCode();
                java.io.InputStream stream = statusCode >= 200 && statusCode < 300
                        ? connection.getInputStream() : connection.getErrorStream();
                ByteArrayOutputStream bytes = new ByteArrayOutputStream();
                byte[] buffer = new byte[2048];
                int count;
                while ((count = stream.read(buffer)) != -1) bytes.write(buffer, 0, count);
                JSONObject result = new JSONObject(new String(bytes.toByteArray(), StandardCharsets.UTF_8));
                if (statusCode < 200 || statusCode >= 300) {
                    throw new Exception(result.optString("error", "Компьютер не найден"));
                }
                String base = result.getString("url");
                String pin = result.getString("pin");
                Uri uri = Uri.parse(base);
                if (!"https".equalsIgnoreCase(uri.getScheme()) || uri.getHost() == null || !uri.getHost().endsWith(".ts.net")) {
                    throw new Exception("Сервер вернул некорректный адрес");
                }
                String fullUrl = base + (base.contains("?") ? "&" : "?") + "pin=" + Uri.encode(pin);
                runOnUiThread(() -> showBrowser(fullUrl));
            } catch (Exception e) {
                String message = e.getMessage() == null ? "Не удалось найти компьютер" : e.getMessage();
                runOnUiThread(() -> status.setText(message));
            } finally {
                if (connection != null) connection.disconnect();
            }
        });
    }

    private void connectManual() {
        String raw = addressInput.getText().toString().trim();
        if (!isPairingUrl(raw)) {
            addressInput.setError("Нужна полная ссылка http:// или https:// с PIN");
            return;
        }
        ((InputMethodManager) getSystemService(INPUT_METHOD_SERVICE))
                .hideSoftInputFromWindow(addressInput.getWindowToken(), 0);
        showBrowser(raw);
    }

    private boolean isPairingUrl(String raw) {
        Uri uri = Uri.parse(raw);
        String scheme = uri.getScheme();
        return scheme != null
                && (scheme.equalsIgnoreCase("http") || scheme.equalsIgnoreCase("https"))
                && uri.getHost() != null
                && uri.getQueryParameter("pin") != null
                && !uri.getQueryParameter("pin").isEmpty();
    }

    private void showBrowser(String url) {
        stopDiscovery();
        Uri startUri = Uri.parse(url);
        allowRemotePage = "/remote".equals(startUri.getPath());
        allowedHost = startUri.getHost() == null ? "" : startUri.getHost().toLowerCase(Locale.ROOT);
        allowedScheme = startUri.getScheme() == null ? "" : startUri.getScheme().toLowerCase(Locale.ROOT);
        allowedPort = startUri.getPort();
        root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(BG);

        LinearLayout top = new LinearLayout(this);
        top.setGravity(Gravity.CENTER_VERTICAL);
        top.setPadding(12, 6, 12, 6);
        top.setBackgroundColor(PANEL);
        Button back = button(sessionToken.isEmpty() ? "← Компьютеры" : "← Панель управления");
        back.setOnClickListener(v -> {
            if (!sessionToken.isEmpty()) {
                showConnectedControls(connectedBaseUrl + "/remote?token=" + Uri.encode(sessionToken));
            } else {
                showHome();
            }
        });
        top.addView(back);
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
                Uri target = request.getUrl();
                if ("/remote".equals(target.getPath()) && target.getQueryParameter("token") != null && !allowRemotePage) {
                    runOnUiThread(() -> showConnectedControls(target.toString()));
                    return true;
                }
                String scheme = target.getScheme() == null ? "" : target.getScheme().toLowerCase(Locale.ROOT);
                String host = target.getHost() == null ? "" : target.getHost().toLowerCase(Locale.ROOT);
                return !(scheme.equals(allowedScheme) && host.equals(allowedHost)
                        && target.getPort() == allowedPort);
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
        stopDiscovery();
        network.shutdownNow();
        if (webView != null) {
            webView.stopLoading();
            webView.destroy();
            webView = null;
        }
        super.onDestroy();
    }
}
