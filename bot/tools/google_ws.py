"""Google Workspace araçları: Gmail, Takvim, Drive, Docs, Sheets."""
from __future__ import annotations

import asyncio
import base64
from datetime import datetime, timedelta
from email.mime.text import MIMEText

from .registry import P, ToolContext, tool
from .web import html_to_text


class NotConnected(Exception):
    pass


def _svc(ctx: ToolContext, name: str, version: str):
    from googleapiclient.discovery import build
    creds = ctx.app.google.credentials()
    if not creds:
        raise NotConnected("Google hesabı bağlı değil. Telegram'da /google komutunu kullan.")
    return build(name, version, credentials=creds, cache_discovery=False)


async def _run(fn):
    return await asyncio.to_thread(fn)


def _header(msg: dict, name: str) -> str:
    for h in msg.get("payload", {}).get("headers", []):
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""


def _body(payload: dict) -> str:
    def walk(p):
        mime = p.get("mimeType", "")
        data = p.get("body", {}).get("data")
        if data and mime in ("text/plain", "text/html"):
            yield mime, base64.urlsafe_b64decode(data + "==").decode("utf-8", "ignore")
        for sub in p.get("parts", []) or []:
            yield from walk(sub)
    parts = list(walk(payload))
    for mime, text in parts:
        if mime == "text/plain":
            return text
    for mime, text in parts:
        return html_to_text(text, 20000)["text"]
    return ""


# ---------------- Gmail ----------------
@tool("gmail_search", "Gmail'de e-posta arar. Gmail arama sözdizimi kullanılır (ör. 'is:unread', 'from:ali', "
      "'newer_than:2d', 'subject:fatura').", "google",
      {"query": P(str, "Gmail arama ifadesi"), "max_results": P(int, "En fazla kaç sonuç (varsayılan 10)", required=False)})
async def gmail_search(ctx: ToolContext, query: str, max_results: int = 10):
    def go():
        s = _svc(ctx, "gmail", "v1")
        ids = s.users().messages().list(userId="me", q=query, maxResults=min(int(max_results), 25)).execute()
        out = []
        for m in ids.get("messages", []):
            msg = s.users().messages().get(userId="me", id=m["id"], format="metadata",
                                           metadataHeaders=["From", "Subject", "Date"]).execute()
            out.append({"id": m["id"], "from": _header(msg, "From"), "subject": _header(msg, "Subject"),
                        "date": _header(msg, "Date"), "snippet": msg.get("snippet", ""),
                        "unread": "UNREAD" in msg.get("labelIds", [])})
        return out
    return await _run(go)


@tool("gmail_read", "Bir e-postanın tam içeriğini okur.", "google", {"message_id": P(str, "E-posta id")})
async def gmail_read(ctx: ToolContext, message_id: str):
    def go():
        s = _svc(ctx, "gmail", "v1")
        msg = s.users().messages().get(userId="me", id=message_id, format="full").execute()
        return {"id": message_id, "thread_id": msg.get("threadId"), "from": _header(msg, "From"),
                "to": _header(msg, "To"), "subject": _header(msg, "Subject"), "date": _header(msg, "Date"),
                "body": _body(msg.get("payload", {}))[:10000]}
    return await _run(go)


def _mime(to: str, subject: str, body: str, thread_id: str | None = None, in_reply_to: str | None = None) -> dict:
    m = MIMEText(body, "plain", "utf-8")
    m["To"], m["Subject"] = to, subject
    if in_reply_to:
        m["In-Reply-To"] = m["References"] = in_reply_to
    raw = {"raw": base64.urlsafe_b64encode(m.as_bytes()).decode()}
    if thread_id:
        raw["threadId"] = thread_id
    return raw


@tool("gmail_draft", "Gmail'de taslak e-posta oluşturur (göndermez).", "google",
      {"to": P(str, "Alıcı adresi"), "subject": P(str, "Konu"), "body": P(str, "Metin")})
async def gmail_draft(ctx: ToolContext, to: str, subject: str, body: str):
    def go():
        s = _svc(ctx, "gmail", "v1")
        d = s.users().drafts().create(userId="me", body={"message": _mime(to, subject, body)}).execute()
        return {"draft_id": d["id"]}
    return await _run(go)


@tool("gmail_send", "E-posta gönderir. Cevap için thread_id verilebilir.", "google",
      {"to": P(str, "Alıcı"), "subject": P(str, "Konu"), "body": P(str, "Metin"),
       "thread_id": P(str, "Cevaplanan konuşma id (isteğe bağlı)", required=False)},
      approval=True, summary=lambda a: f"📧 E-posta gönder\nKime: {a['to']}\nKonu: {a['subject']}\n\n{a['body'][:1500]}")
async def gmail_send(ctx: ToolContext, to: str, subject: str, body: str, thread_id: str | None = None):
    def go():
        s = _svc(ctx, "gmail", "v1")
        r = s.users().messages().send(userId="me", body=_mime(to, subject, body, thread_id)).execute()
        return {"sent_id": r["id"]}
    return await _run(go)


@tool("gmail_mark_read", "E-postayı okundu olarak işaretler.", "google", {"message_id": P(str, "E-posta id")})
async def gmail_mark_read(ctx: ToolContext, message_id: str):
    def go():
        _svc(ctx, "gmail", "v1").users().messages().modify(
            userId="me", id=message_id, body={"removeLabelIds": ["UNREAD"]}).execute()
        return {"ok": True}
    return await _run(go)


@tool("gmail_trash", "E-postayı çöp kutusuna taşır.", "google", {"message_id": P(str, "E-posta id")}, approval=True,
      summary=lambda a: f"🗑️ E-postayı çöpe taşı ({a['message_id']})")
async def gmail_trash(ctx: ToolContext, message_id: str):
    def go():
        _svc(ctx, "gmail", "v1").users().messages().trash(userId="me", id=message_id).execute()
        return {"ok": True}
    return await _run(go)


# ---------------- Takvim ----------------
def _iso(dt: str, tz) -> dict:
    """'2026-11-20 14:00' veya '2026-11-20' → Google takvim zaman nesnesi."""
    dt = dt.strip().replace("T", " ")
    if len(dt) == 10:
        return {"date": dt}
    parsed = datetime.fromisoformat(dt)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=tz)
    return {"dateTime": parsed.isoformat()}


@tool("calendar_list", "Takvimdeki yaklaşan etkinlikleri listeler.", "google",
      {"days": P(int, "Kaç gün ileriye bakılsın (varsayılan 1)", required=False),
       "query": P(str, "Arama metni (isteğe bağlı)", required=False)})
async def calendar_list(ctx: ToolContext, days: int = 1, query: str | None = None):
    tz = ctx.app.cfg.tz
    def go():
        s = _svc(ctx, "calendar", "v3")
        now = datetime.now(tz)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        r = s.events().list(calendarId="primary", timeMin=start.isoformat(),
                            timeMax=(now + timedelta(days=int(days))).isoformat(), singleEvents=True,
                            orderBy="startTime", q=query, maxResults=50).execute()
        return [{"id": e["id"], "title": e.get("summary", "(başlıksız)"),
                 "start": e["start"].get("dateTime", e["start"].get("date")),
                 "end": e["end"].get("dateTime", e["end"].get("date")),
                 "location": e.get("location", ""), "attendees": len(e.get("attendees", []))}
                for e in r.get("items", [])]
    return await _run(go)


@tool("calendar_create", "Takvime etkinlik ekler. Zaman biçimi: 'YYYY-AA-GG SS:DD' veya tüm gün için 'YYYY-AA-GG'.",
      "google", {"title": P(str, "Başlık"), "start": P(str, "Başlangıç"), "end": P(str, "Bitiş"),
                 "description": P(str, "Açıklama", required=False), "location": P(str, "Yer", required=False),
                 "attendees": P("array", "Davet edilecek e-postalar (davet gönderilir)", required=False)},
      approval=lambda a: bool(a.get("attendees")),
      summary=lambda a: f"📅 Etkinlik + davet gönder: {a['title']} ({a['start']})\nDavetliler: {', '.join(a.get('attendees') or [])}")
async def calendar_create(ctx: ToolContext, title: str, start: str, end: str, description: str = "",
                          location: str = "", attendees: list | None = None):
    tz = ctx.app.cfg.tz
    def go():
        body = {"summary": title, "description": description, "location": location,
                "start": _iso(start, tz), "end": _iso(end, tz)}
        if attendees:
            body["attendees"] = [{"email": a} for a in attendees]
        e = _svc(ctx, "calendar", "v3").events().insert(
            calendarId="primary", body=body, sendUpdates="all" if attendees else "none").execute()
        return {"event_id": e["id"], "link": e.get("htmlLink")}
    return await _run(go)


@tool("calendar_delete", "Takvimden etkinlik siler.", "google", {"event_id": P(str, "Etkinlik id")}, approval=True,
      summary=lambda a: f"🗑️ Takvim etkinliğini sil ({a['event_id']})")
async def calendar_delete(ctx: ToolContext, event_id: str):
    def go():
        _svc(ctx, "calendar", "v3").events().delete(calendarId="primary", eventId=event_id).execute()
        return {"ok": True}
    return await _run(go)


# ---------------- Drive / Docs / Sheets ----------------
@tool("drive_search", "Google Drive'da dosya arar (ad veya içerik).", "google", {"query": P(str, "Aranan kelime")})
async def drive_search(ctx: ToolContext, query: str):
    def go():
        q = query.replace("'", "\\'")
        r = _svc(ctx, "drive", "v3").files().list(
            q=f"(name contains '{q}' or fullText contains '{q}') and trashed=false", pageSize=15,
            fields="files(id,name,mimeType,modifiedTime,webViewLink)").execute()
        return r.get("files", [])
    return await _run(go)


@tool("drive_read", "Drive dosyasının metnini okur (Docs, Sheets, metin, PDF dışı).", "google",
      {"file_id": P(str, "Dosya id")})
async def drive_read(ctx: ToolContext, file_id: str):
    def go():
        s = _svc(ctx, "drive", "v3")
        meta = s.files().get(fileId=file_id, fields="name,mimeType").execute()
        mime = meta["mimeType"]
        if mime == "application/vnd.google-apps.document":
            data = s.files().export(fileId=file_id, mimeType="text/plain").execute()
        elif mime == "application/vnd.google-apps.spreadsheet":
            data = s.files().export(fileId=file_id, mimeType="text/csv").execute()
        elif mime == "application/vnd.google-apps.presentation":
            data = s.files().export(fileId=file_id, mimeType="text/plain").execute()
        elif mime.startswith("text/") or mime in ("application/json",):
            data = s.files().get_media(fileId=file_id).execute()
        else:
            return {"name": meta["name"], "mimeType": mime, "error": "Bu dosya türü metin olarak okunamıyor"}
        text = data.decode("utf-8", "ignore") if isinstance(data, bytes) else str(data)
        return {"name": meta["name"], "text": text[:15000]}
    return await _run(go)


@tool("docs_create", "Yeni Google Docs belgesi oluşturur ve içine metin yazar.", "google",
      {"title": P(str, "Belge başlığı"), "content": P(str, "Belge metni")})
async def docs_create(ctx: ToolContext, title: str, content: str):
    def go():
        d = _svc(ctx, "docs", "v1")
        doc = d.documents().create(body={"title": title}).execute()
        d.documents().batchUpdate(documentId=doc["documentId"], body={"requests": [
            {"insertText": {"location": {"index": 1}, "text": content}}]}).execute()
        return {"document_id": doc["documentId"], "link": f"https://docs.google.com/document/d/{doc['documentId']}/edit"}
    return await _run(go)


@tool("sheets_read", "Google Sheets tablosundan aralık okur (ör. 'Sayfa1!A1:D20').", "google",
      {"spreadsheet_id": P(str, "Tablo id"), "range": P(str, "Aralık")})
async def sheets_read(ctx: ToolContext, spreadsheet_id: str, range: str):
    def go():
        r = _svc(ctx, "sheets", "v4").spreadsheets().values().get(spreadsheetId=spreadsheet_id, range=range).execute()
        return {"values": r.get("values", [])[:200]}
    return await _run(go)


@tool("sheets_append", "Google Sheets tablosunun sonuna satır ekler.", "google",
      {"spreadsheet_id": P(str, "Tablo id"), "range": P(str, "Sayfa/aralık, ör. 'Sayfa1!A:D'"),
       "rows": P("array", "Eklenecek satırlar; her satır virgülle ayrılmış metin, ör. '2026-11-15,Market,250'")})
async def sheets_append(ctx: ToolContext, spreadsheet_id: str, range: str, rows: list):
    def go():
        values = [r.split(",") if isinstance(r, str) else r for r in rows]
        r = _svc(ctx, "sheets", "v4").spreadsheets().values().append(
            spreadsheetId=spreadsheet_id, range=range, valueInputOption="USER_ENTERED",
            body={"values": values}).execute()
        return {"updated": r.get("updates", {}).get("updatedRows", 0)}
    return await _run(go)


@tool("sheets_create", "Yeni Google Sheets tablosu oluşturur.", "google",
      {"title": P(str, "Tablo adı"), "header": P("array", "Başlık satırı sütunları", required=False)})
async def sheets_create(ctx: ToolContext, title: str, header: list | None = None):
    def go():
        s = _svc(ctx, "sheets", "v4")
        sh = s.spreadsheets().create(body={"properties": {"title": title}}).execute()
        sid = sh["spreadsheetId"]
        if header:
            s.spreadsheets().values().update(spreadsheetId=sid, range="A1", valueInputOption="RAW",
                                             body={"values": [header]}).execute()
        return {"spreadsheet_id": sid, "link": sh.get("spreadsheetUrl")}
    return await _run(go)
