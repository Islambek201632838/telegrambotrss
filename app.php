<?php
// Import necessary libraries
require 'vendor/autoload.php'; // Composer for libraries like Guzzle, if needed

use DateTime;
use DateInterval;
use DOMDocument;
use TelegramBot\Api\BotApi;

// Configuration
define('BOT_TOKEN', '7938419408:AAGb5tk-OmWCoVuAKv5xLOPNjUElB0_g4i0');
define('GROUP_CHAT_ID', '@totalaboutai');
define('RSS_URL', 'https://rss.app/feeds/tGAHaxSKFrb2nodC.xml');
define('COOLDOWN', 'PT1M'); // ISO8601 interval for 1 minute

// Variables to track state
$latestPublished = null;
$pendingEntries = [];
$lastPostTime = null;

// Logging setup
function logMessage($message)
{
    $log = date('Y-m-d H:i:s') . " - $message" . PHP_EOL;
    file_put_contents('bot.log', $log, FILE_APPEND);
}

// Function to fetch RSS feed and process it
function checkAndPost($bot)
{
    global $latestPublished, $pendingEntries, $lastPostTime;

    // Fetch RSS feed
    $rssContent = file_get_contents(RSS_URL);
    if (!$rssContent) {
        logMessage('Failed to fetch RSS feed.');
        return;
    }

    // Parse RSS feed
    $dom = new DOMDocument();
    @$dom->loadXML($rssContent); // Suppress warnings if feed is invalid

    $items = $dom->getElementsByTagName('item');
    $newEntries = [];

    foreach ($items as $item) {
        $title = $item->getElementsByTagName('title')->item(0)->nodeValue ?? 'Untitled';
        $link = $item->getElementsByTagName('link')->item(0)->nodeValue ?? '';
        $description = $item->getElementsByTagName('description')->item(0)->nodeValue ?? '';
        $pubDate = $item->getElementsByTagName('pubDate')->item(0)->nodeValue ?? '';

        $pubTime = new DateTime($pubDate);
        if ($latestPublished === null || $pubTime > $latestPublished) {
            $newEntries[] = [
                'title' => $title,
                'link' => $link,
                'description' => $description,
                'pubDate' => $pubTime
            ];
        }
    }

    if ($newEntries) {
        usort($newEntries, function ($a, $b) {
            return $a['pubDate'] <=> $b['pubDate'];
        });
        $pendingEntries = array_merge($pendingEntries, $newEntries);
        $latestPublished = max(array_column($newEntries, 'pubDate'));
    }

    // Check cooldown
    $now = new DateTime();
    if ($lastPostTime === null || $now > $lastPostTime->add(new DateInterval(COOLDOWN))) {
        if (!empty($pendingEntries)) {
            $entryToPost = array_shift($pendingEntries);
            $title = htmlspecialchars($entryToPost['title'], ENT_QUOTES | ENT_HTML5);
            $description = htmlspecialchars(strip_tags($entryToPost['description']), ENT_QUOTES | ENT_HTML5);
            $link = $entryToPost['link'];

            $message = "<b>$title</b>\n\n$description\n\n<a href=\"$link\">Подробнее</a>";

            // Send message
            try {
                $bot->sendMessage(GROUP_CHAT_ID, $message, 'HTML');
                logMessage("Posted: $title");
                $lastPostTime = $now;
            } catch (Exception $e) {
                logMessage('Error posting to Telegram: ' . $e->getMessage());
            }
        } else {
            logMessage('No items in queue to post.');
        }
    } else {
        logMessage('Cooling down...');
    }
}

// Main function
function main()
{
    $bot = new BotApi(BOT_TOKEN);

    // Run every 30 seconds
    while (true) {
        checkAndPost($bot);
        sleep(30);
    }
}

main();
