import os
import time
from datetime import datetime
import pytz
import requests
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

load_dotenv()
pw = os.getenv("pw")
telegram_token = os.getenv("TELEGRAM_TOKEN")
telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")
wib = datetime.now(pytz.timezone("Asia/Jakarta")).strftime("%Y-%m-%d %H:%M WIB")

def baca_file(file_name: str) -> str:
    with open(file_name, 'r') as file:
        return file.read().strip()

def kirim_telegram(pesan: str):
    print(pesan)
    if telegram_token and telegram_chat_id:
        try:
            response = requests.post(
                f"https://api.telegram.org/bot{telegram_token}/sendMessage",
                data={
                    "chat_id": telegram_chat_id,
                    "text": pesan,
                    "parse_mode": "HTML"
                }
            )
            if response.status_code != 200:
                print(f"Gagal kirim ke Telegram. Status: {response.status_code}")
        except Exception as e:
            print("Error saat kirim ke Telegram:", e)

def parse_saldo(text: str) -> float:
    text = text.replace("Rp.", "").replace("Rp", "").strip().replace(",", "")
    try:
        return float(text)
    except:
        return 0.0

def lakukan_wd(page, situs, jumlah_wd):
    try:
        page.goto(f"https://{situs}/#/mine", timeout=30000)
        page.get_by_role("img", name="withdrawal").click()
        page.get_by_role("textbox", name="Minimum jumlah penarikan:").fill(jumlah_wd)
        page.get_by_text("kirim", exact=True).click()
        time.sleep(2)
        return True
    except Exception as e:
        print("Gagal WD:", e)
        return False

def cek_status_wd(page, situs):
    try:
        page.goto(f"https://{situs}/#/mine", timeout=30000)
        page.locator("#mine").get_by_text("History Transaksi").click()
        page.get_by_text("Withdraw", exact=True).click()
        time.sleep(2)

        item = page.locator(".list .item").first
        nominal_text = item.locator(".right b").inner_text().strip()
        status_text = item.locator(".right i").inner_text().strip()
        tanggal_text = item.locator(".center i").inner_text().strip()
        nominal = nominal_text.replace("<u>Rp</u>", "").replace("Rp", "").replace(",", "").strip()

        return status_text, nominal, tanggal_text
    except Exception as e:
        print("Gagal cek status WD:", e)
        return "Gagal cek", "-", "-"

def cek_saldo_dan_status(playwright, situs, userid):
    try:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        page.goto(f"https://{situs}/#/mine", wait_until="domcontentloaded", timeout=60000)

        page.locator("input#loginUser").wait_for()
        page.locator("input#loginUser").type(userid, delay=100)
        page.locator("input#loginPsw").type(pw, delay=120)
        page.locator("div.login-btn").click()

        try:
            page.get_by_role("link", name="Saya Setuju").click()
        except:
            pass

        time.sleep(3)

        # Ambil saldo
        saldo_text = page.locator(".myPurse span i").inner_text().strip()
        saldo_value = parse_saldo(saldo_text)

        # Ambil nama permainan terbaru
        page.goto(f"https://{situs}/#/betRecords")
        page.get_by_text("Togel").click()
        page.locator(".list .ls-list-item").first.wait_for(timeout=10000)
        nama_permainan = page.locator(".list .ls-list-item").first.locator("li").nth(2).inner_text().strip()

        status_permainan = "🏆 Menang" if "Menang" in nama_permainan else "🥲 Tidak menang"

        # Kirim status awal
        kirim_telegram(
            f"<b>[STATUS]</b>\n"
            f"👤 {userid}\n"
            f"💰 SALDO: <b>Rp {saldo_value:,.0f}</b>\n"
            f"{status_permainan}\n"
            f"⌚ {wib}"
        )

        # Cek apakah auto-WD perlu dilakukan
        if os.path.exists("target.txt"):
            target_line = baca_file("target.txt")
            if '|' in target_line:
                target_saldo_str, jumlah_wd_str = target_line.split('|')
                target_saldo = float(target_saldo_str)
                jumlah_wd = jumlah_wd_str.strip()

                if saldo_value >= target_saldo:
                    berhasil_wd = lakukan_wd(page, situs, jumlah_wd)
                    if berhasil_wd:
                        time.sleep(5)
                        status, nominal, tanggal = cek_status_wd(page, situs)
                        kirim_telegram(
                            f"<b>[AUTO-WD]</b>\n"
                            f"👤 {userid}\n"
                            f"💸 Rp {nominal}\n"
                            f"📆 {tanggal}\n"
                            f"✅ Status: <b>{status}</b>\n"
                            f"⌚ {wib}"
                        )

        context.close()
        browser.close()

    except Exception as e:
        kirim_telegram(f"<b>[ERROR]</b>\n👤 {userid}\n❌ {e}\n⌚ {wib}")

def run(playwright, situs, userid, *_):
    cek_saldo_dan_status(playwright, situs, userid)

def main():
    bets = baca_file("multi.txt").splitlines()
    with sync_playwright() as playwright:
        for baris in bets:
            if '|' not in baris or baris.strip().startswith("#"):
                continue
            parts = baris.strip().split('|')
            if len(parts) < 5:
                continue
            situs, userid, bet_raw, bet_raw2, config_csv = parts
            run(playwright, situs.strip(), userid.strip(), bet_raw.strip(), bet_raw2.strip(), config_csv.strip())

if __name__ == "__main__":
    main()
