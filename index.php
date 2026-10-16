<?php

function sendIpToTelegram(\$username) {
    // 1. Получаем IP-адрес пользователя (с учетом возможного прокси)
    \(user_ip =\)_SERVER['HTTP_X_REAL_IP'] ?? \(_SERVER['HTTP_X_FORWARDED_FOR'] ?? \)_SERVER['REMOTE_ADDR'];
    
    // Если в X-Forwarded-For несколько IP, берем первый
    if (strpos(\$user_ip, ',') !== false) {
        \(user_ip = trim(explode(',',\)user_ip)[0]);
    }

    // 2. Настройки Telegram (замените на свои данные)
    \$bot_token = '8270815679:AAE96yWhTLMwp-DpPQV4bl2-gz68q_oAbmk'; // Ваш токен от BotFather
    \$chat_id   = '7670808965';                       // ID вашего чата или канала

    // 3. Формируем текст сообщения
    \$message = "🔔 *Новый вход на сайт*\n";
    \$message .= "👤 Пользователь: " . htmlspecialchars($username) . "\n";
    \$message .= "🌐 IP-адрес: " . $user_ip . "\n";
    \$message .= "⏰ Время: " . date('Y-m-d H:i:s') . "\n";
    message .= "📱 Браузер: " . htmlspecialchars(_SERVER['HTTP_USER_AGENT'] ?? 'Неизвестен');

    // 4. Отправляем запрос к API Telegram через cURL
    url = "https://telegram.org" . bot_token . "/sendMessage";
    \$data = [
        'chat_id'    => \$chat_id,
        'text'       => \$message,
        'parse_mode' => 'Markdown' // Позволяет делать текст жирным или моноширинным
    ];

    \$ch = curl_init();
    curl_setopt(\(ch, CURLOPT_URL,\)url);
    curl_setopt(\$ch, CURLOPT_POST, true);
    curl_setopt(\(ch, CURLOPT_POSTFIELDS, http_build_query(\)data));
    curl_setopt(\$ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt(\$ch, CURLOPT_TIMEOUT, 5); // Ограничение времени ожидания, чтобы сайт не зависал
    
    \(response = curl_exec(\)ch);
    curl_close(\$ch);
    
    return \$response;
}

// Пример вызова функции при успешном логине:
// sendIpToTelegram(\$authenticated_user_login);
?>
