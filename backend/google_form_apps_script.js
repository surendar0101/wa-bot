/**
 * Google Apps Script — attach to the Form's linked Google Sheet
 *
 * Setup:
 * 1. Open Form → Responses → Link to Sheets
 * 2. Extensions → Apps Script → paste this file
 * 3. Project Settings → Script properties:
 *      WEBHOOK_URL = https://YOUR-NGROK-OR-SERVER/api/webhooks/form-intake
 *      WEBHOOK_SECRET = same as FORM_WEBHOOK_SECRET in backend/.env
 * 4. Triggers → Add → onFormSubmit → onFormSubmit
 *
 * Column order must match your form (adjust indices if you reorder fields):
 * [0] Timestamp
 * [1] Name
 * [2] Service
 * [3] Call format (audio/video)
 * [4] Investment amount
 * [5] WhatsApp phone
 * [6] Understood (yes)
 * [7] Premium / Regular
 */

function onFormSubmit(e) {
  var row = e.values;
  var payload = {
    submitted_at: row[0],
    name: row[1],
    service: row[2],
    call_format: row[3],
    investment_amount: row[4],
    phone: row[5],
    consultation_tier: row[7],
    form_id: "1FAIpQLSfQ7V70Sf-KszsDymyD3KBZ57nNJksavCfiEb75C9U4N0Bffg",
  };

  var props = PropertiesService.getScriptProperties();
  var url = props.getProperty("WEBHOOK_URL");
  var secret = props.getProperty("WEBHOOK_SECRET");
  if (!url || !secret) {
    console.error("Set WEBHOOK_URL and WEBHOOK_SECRET in Script properties");
    return;
  }

  var options = {
    method: "post",
    contentType: "application/json",
    headers: { "X-Webhook-Secret": secret },
    payload: JSON.stringify(payload),
    muteHttpExceptions: true,
  };

  var res = UrlFetchApp.fetch(url, options);
  console.log(res.getResponseCode(), res.getContentText());
}
