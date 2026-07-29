/**
 * Бесплатная отправка писем через твой Gmail (Google Apps Script).
 *
 * 1. https://script.google.com → New project
 * 2. Вставь этот код, замени SECRET ниже
 * 3. Deploy → New deployment → Web app
 *    - Execute as: Me
 *    - Who has access: Anyone
 * 4. Скопируй URL в Railway: EMAIL_WEBHOOK_URL
 *    EMAIL_WEBHOOK_SECRET = тот же SECRET
 */

const SECRET = "change-me-to-a-long-random-string";

function doPost(e) {
  try {
    const data = JSON.parse(e.postData.contents);
    if (!data.secret || data.secret !== SECRET) {
      return json_({ ok: false, error: "unauthorized" });
    }
    if (!data.to || !data.subject || !data.html) {
      return json_({ ok: false, error: "missing fields" });
    }
    GmailApp.sendEmail(String(data.to), String(data.subject), "", {
      htmlBody: String(data.html),
      name: String(data.fromName || "Contact API"),
    });
    return json_({ ok: true });
  } catch (err) {
    return json_({ ok: false, error: String(err) });
  }
}

function json_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(
    ContentService.MimeType.JSON
  );
}
