import asyncio
import websockets
import json
import sys
import datetime
import aiohttp
import keyboard
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.live import Live
from rich import box

# Konfigurasi headers untuk request
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
    "Origin": "chrome-extension://emcclcoaglgcpoognfiggmhnhgabppkm",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7"
}

# Global variables untuk menyimpan status dan data
status_dict = {}
status_lock = asyncio.Lock()
status_event = {}
ordered_tokens = []
console = Console()

# Pagination variables
tokens_per_page = 50  # Number of tokens to show per page
current_page = 0      # Current page index
page_lock = asyncio.Lock()  # Lock for modifying page

# Animasi untuk menampilkan status koneksi
status_animations = {
    "CONNECTED": "✅ ",
    "PING": "🔄 ",
    "RECEIVED": "📩 ",
    "ERROR": "❌ ",
    "CLOSED": "🔒 "
}

# Warna untuk berbagai status
status_colors = {
    "CONNECTED": "green",
    "PING": "blue",
    "RECEIVED": "yellow",
    "ERROR": "red",
    "CLOSED": "magenta"
}

# Menggunakan layout untuk membagi layar menjadi beberapa bagian
def create_layout():
    layout = Layout()
    layout.split(
        Layout(name="header", size=3),
        Layout(name="main"),
        Layout(name="pagination_info", size=1),
        Layout(name="footer", size=3)
    )
    return layout

# Membuat header dengan judul aplikasi
def make_header():
    grid = Table.grid(expand=True)
    grid.add_column(justify="center", ratio=1)
    grid.add_row("[bold cyan]TENEO WEBSOCKET MONITOR[/bold cyan]")
    return Panel(grid, style="cyan", box=box.ROUNDED)

# Membuat pagination info
def make_pagination_info():
    total_pages = (len(ordered_tokens) + tokens_per_page - 1) // tokens_per_page
    return f"[yellow]Page {current_page + 1}/{total_pages} - Use LEFT/RIGHT arrows to navigate pages[/yellow]"

# Membuat footer dengan informasi tambahan
def make_footer():
    grid = Table.grid(expand=True)
    grid.add_column(justify="left", ratio=1)
    grid.add_column(justify="right", ratio=1)
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    grid.add_row(
        f"[yellow]Total Tokens: {len(ordered_tokens)}[/yellow]",
        f"[blue]{now}[/blue]"
    )
    return Panel(grid, style="cyan", box=box.ROUNDED)

# Membuat tabel utama yang menampilkan status dari semua token
def make_main_table():
    table = Table(
        show_header=True,
        header_style="bold cyan",
        box=box.ROUNDED,
        expand=True,
        title="[bold]Teneo Token Monitor[/bold]",
        title_style="cyan",
        caption="[dim]Use LEFT/RIGHT arrows to navigate pages[/dim]",
        caption_style="dim"
    )
    
    table.add_column("Token", style="cyan", no_wrap=True)
    table.add_column("Heart Beats", style="magenta")
    table.add_column("Points Today", style="yellow")
    table.add_column("Points Total", style="green")
    table.add_column("Status", style="blue")
    table.add_column("Last Message", style="white")
    table.add_column("Last Updated", style="dim")
    
    # Calculate which tokens to display on the current page
    start_idx = current_page * tokens_per_page
    end_idx = min(start_idx + tokens_per_page, len(ordered_tokens))
    current_page_tokens = ordered_tokens[start_idx:end_idx]
    
    for token in current_page_tokens:
        events = status_event.get(token, {})
        short_token = token[:7] + '...' + token[-7:] if len(token) > 20 else token
        
        # Default values
        heart_beats = "-"
        points_today = "-"
        points_total = "-" 
        status_display = "[dim]Waiting...[/dim]"
        message = "-"
        updated_time = "-"
        
        # Prioritize getting heartbeats from CONNECTED event
        if "CONNECTED" in events:
            updated_time, msg, _, pt, ptot, extra = events["CONNECTED"]
            if extra and isinstance(extra, (int, str)) and extra != "-":
                heart_beats = str(extra)
            if pt is not None:
                points_today = str(pt)
            if ptot is not None:
                points_total = str(ptot)
            message = msg or "-"
            
        # Get the most recent event for status display
        last_event = None
        for evt in ["RECEIVED", "ERROR", "CLOSED", "CONNECTED", "PING"]:
            if evt in events:
                evt_time, evt_msg, _, _, _, _ = events[evt]
                if evt != "CONNECTED":  # Only update message if not CONNECTED (we already got that)
                    if last_event is None or evt_time > last_event[1]:
                        last_event = (evt, evt_time)
        
        # Set status display from the most recent event
        if last_event:
            evt_name, _ = last_event
            status_display = f"[{status_colors[evt_name]}]{status_animations[evt_name]}{evt_name}[/{status_colors[evt_name]}]"
        
        table.add_row(
            f"[bold cyan]{short_token}[/bold cyan]",
            f"[magenta]{heart_beats}[/magenta]",
            f"[yellow]{points_today}[/yellow]",
            f"[green]{points_total}[/green]",
            status_display,
            message,
            updated_time
        )
    
    return table

# Handle keyboard input for pagination
async def handle_keyboard_input():
    global current_page
    
    while True:
        await asyncio.sleep(0.1)  # Check less frequently to reduce CPU usage
        
        # Using python-keyboard library for keyboard input
        # LEFT arrow key - previous page
        if keyboard.is_pressed('left'):
            async with page_lock:
                if current_page > 0:
                    current_page -= 1
            await asyncio.sleep(0.2)  # Prevent too rapid changes
                
        # RIGHT arrow key - next page
        elif keyboard.is_pressed('right'):
            async with page_lock:
                total_pages = (len(ordered_tokens) + tokens_per_page - 1) // tokens_per_page
                if current_page < total_pages - 1:
                    current_page += 1
            await asyncio.sleep(0.2)  # Prevent too rapid changes

# Generator untuk efek visual random saat koneksi aktif
def generate_activity_indicator():
    indicators = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
    i = 0
    while True:
        yield indicators[i]
        i = (i + 1) % len(indicators)

# Update status untuk token dan event tertentu
async def update_status(token, event, message, color="white", points_today=None, points_total=None, extra_msg=None):
    async with status_lock:
        # Always update the timestamp to the current time
        now = datetime.datetime.now().strftime('%H:%M:%S')
        
        if token not in status_event:
            status_event[token] = {}
        
        # Preserve heartbeats for CONNECTED events
        if event == "CONNECTED":
            # If there's an existing CONNECTED event with heartbeats, preserve it
            if "CONNECTED" in status_event[token]:
                old_time, old_msg, old_color, old_pt, old_ptot, old_extra = status_event[token]["CONNECTED"]
                # Only update the heartbeats if the new event has it, otherwise keep the old one
                if extra_msg is None and old_extra is not None and str(old_extra).isdigit():
                    extra_msg = old_extra
            
            # Update points if they're provided
            if points_today is None and "CONNECTED" in status_event[token]:
                _, _, _, old_pt, _, _ = status_event[token]["CONNECTED"]
                points_today = old_pt
                
            if points_total is None and "CONNECTED" in status_event[token]:
                _, _, _, _, old_ptot, _ = status_event[token]["CONNECTED"]
                points_total = old_ptot
        
        # Simpan data event baru dengan timestamp terbaru
        status_event[token][event] = (now, message, color, points_today, points_total, extra_msg)
        
        # Jika extra_msg berisi heartbeats, simpan juga di event CONNECTED
        if extra_msg is not None and event != "CONNECTED" and str(extra_msg).isdigit():
            # Update heartbeats in CONNECTED event without changing other data except timestamp
            if "CONNECTED" in status_event[token]:
                _, old_msg, old_color, old_pt, old_ptot, _ = status_event[token]["CONNECTED"]
                # Update the timestamp here too for the CONNECTED event
                status_event[token]["CONNECTED"] = (now, old_msg, old_color, old_pt, old_ptot, extra_msg)

# Fungsi untuk mengirim ping ke server WebSocket
async def send_ping(ws, token):
    """Mengirim ping ke server setiap 10 detik dan update data stats"""
    try:
        while True:
            # Get current time for display
            current_time = datetime.datetime.now().strftime('%H:%M:%S')
            
            # 1. Kirim ping message ke WebSocket
            msg = {"type": "PING"}
            await ws.send(json.dumps(msg))
            await update_status(token, "PING", f"Ping sent at {current_time}")
            
            # 2. Fetch latest stats dari API untuk update data
            try:
                stats = await fetch_user_stats(token)
                if "error" not in stats:
                    heartbeats = stats.get("heartbeats")
                    points_today = stats.get("points_today")
                    points_total = stats.get("points_total")
                    
                    # Update status dengan data terbaru dan pesan yang menunjukkan update time
                    await update_status(token, "CONNECTED", f"Data refreshed at {current_time}", 
                                      points_today=points_today, 
                                      points_total=points_total,
                                      extra_msg=heartbeats)
                    
                    # console.print(f"[dim]Ping update for {token[:7]}...: Heartbeats={heartbeats}, Points Today={points_today}, Total={points_total}[/dim]")
                else:
                    console.print(f"[dim]Error updating stats: {stats.get('error')}[/dim]")
            except Exception as e:
                console.print(f"[dim]Failed to update stats during ping: {str(e)}[/dim]")
            
            # Tunggu tepat 10 detik sebelum ping berikutnya
            await asyncio.sleep(10)
    except asyncio.CancelledError:
        # Tangani pembatalan dengan anggun
        raise
    except Exception as e:
        await update_status(token, "ERROR", f"Ping error: {str(e)}")
        raise  # Re-raise untuk menangani di tingkat atas

# Fungsi untuk mendapatkan statistik pengguna
async def fetch_user_stats(token):
    url = "https://api.teneo.pro/api/users/stats"
    headers_stats = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers_stats) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    # console.print(f"[dim]Stats fetched for {token[:7]}... : {data}[/dim]")
                    return data
                else:
                    return {"error": f"HTTP {resp.status}"}
    except Exception as e:
        return {"error": str(e)}

# Fungsi untuk menerima pesan dari WebSocket
async def receive_messages(ws, token):
    """Menerima dan memproses pesan dari WebSocket"""
    try:
        async for message in ws:
            points_today = points_total = extra_msg = None
            try:
                data = json.loads(message)
                # Log message untuk debugging
                # console.print(f"[dim]Received for {token[:7]}...: {data}[/dim]")
                
                # Ekstrak informasi penting
                points_today = data.get('pointsToday')
                points_total = data.get('pointsTotal')
                extra_msg = data.get('message') or data.get('heartbeats')
                
                # Jika ada heartbeats dalam data, update status
                if 'heartbeats' in data:
                    extra_msg = data.get('heartbeats')
                    # Khusus perbarui heart beats
                    await update_status(token, "CONNECTED", "Heartbeats updated", 
                                      points_today=points_today, 
                                      points_total=points_total,
                                      extra_msg=extra_msg)
                
            except Exception as e:
                extra_msg = f"Parse error: {str(e)}, raw: {message[:50]}..."
            
            # Update status umum untuk semua pesan
            await update_status(token, "RECEIVED", f"Received data", 
                              points_today=points_today, 
                              points_total=points_total, 
                              extra_msg=extra_msg)
    except websockets.ConnectionClosed as e:
        await update_status(token, "CLOSED", f"Connection closed: {str(e)}")
        raise  # Re-raise untuk menangani di tingkat atas
    except asyncio.CancelledError:
        # Tangani pembatalan dengan anggun
        raise
    except Exception as e:
        await update_status(token, "ERROR", f"Receive error: {str(e)}")
        raise  # Re-raise untuk menangani di tingkat atas

# Menjalankan koneksi untuk setiap token
async def run_token(token):
    url = f"wss://secure.ws.teneo.pro/websocket?accessToken={token}&version=v0.2"
    while True:
        try:
            # Ambil stats terlebih dahulu
            stats = await fetch_user_stats(token)
            
            if "error" in stats:
                await update_status(token, "ERROR", f"Stats error: {stats['error']}")
            else:
                # Pastikan heartbeats disimpan
                heartbeats = stats.get("heartbeats")
                points_today = stats.get("points_today")
                points_total = stats.get("points_total")
                
                # Log data untuk debugging
                # console.print(f"[dim]Token {token[:7]}...: Heartbeats={heartbeats}, Points Today={points_today}, Total={points_total}[/dim]")
                
                # Simpan informasi statistik dengan heartbeats
                await update_status(token, "CONNECTED", "Fetched stats", 
                                    points_today=points_today,
                                    points_total=points_total,
                                    extra_msg=heartbeats)
            
            # Buat koneksi websocket
            async with websockets.connect(url, extra_headers=headers) as ws:
                # Update status dengan "Connected successfully!" sambil mempertahankan heartbeats
                # yang sudah disimpan sebelumnya dari stats API
                await update_status(token, "CONNECTED", "Connected successfully!")
                
                # Jalankan ping dan listener secara bersamaan
                ping_task = asyncio.create_task(send_ping(ws, token))
                receive_task = asyncio.create_task(receive_messages(ws, token))
                
                try:
                    # Tunggu sampai salah satu task selesai
                    done, pending = await asyncio.wait(
                        [ping_task, receive_task],
                        return_when=asyncio.FIRST_COMPLETED
                    )
                    
                    # Batalkan task yang masih berjalan
                    for task in pending:
                        task.cancel()
                        
                    # Periksa apakah ada error
                    for task in done:
                        if task.exception():
                            raise task.exception()
                            
                except Exception as e:
                    await update_status(token, "ERROR", f"Task error: {str(e)}")
                finally:
                    # Pastikan semua task dibatalkan
                    for task in [ping_task, receive_task]:
                        if not task.done():
                            task.cancel()
                
        except websockets.exceptions.ConnectionClosed as e:
            await update_status(token, "CLOSED", f"Connection closed: {str(e)}")
            await asyncio.sleep(5)
        except Exception as e:
            await update_status(token, "ERROR", f"Connection error: {str(e)}")
            await asyncio.sleep(5)  # Tunggu 5 detik sebelum reconnect

# Fungsi utama untuk menjalankan aplikasi
async def main():
    global ordered_tokens
    
    # Baca token dari file
    try:
        with open("token.txt") as f:
            tokens = [line.strip() for line in f if line.strip()]
        ordered_tokens = tokens.copy()
        
        if not tokens:
            console.print("[bold red]Error:[/bold red] No tokens found in token.txt", style="red")
            return
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] Could not read token.txt: {str(e)}", style="red")
        return
    
    # Setup layout
    layout = create_layout()
    layout["header"].update(make_header())
    layout["footer"].update(make_footer())
    
    # Start monitoring dengan create_task
    tasks = [asyncio.create_task(run_token(token)) for token in tokens]
    
    # Add keyboard handling task
    keyboard_task = asyncio.create_task(handle_keyboard_input())
    
    try:
        # Continuously update the display
        with Live(layout, refresh_per_second=4, screen=True) as live:
            while True:
                # Update main table
                layout["main"].update(make_main_table())
                # Update pagination info
                layout["pagination_info"].update(make_pagination_info())
                # Update footer time
                layout["footer"].update(make_footer())
                await asyncio.sleep(0.25)
    except KeyboardInterrupt:
        console.print("[bold yellow]Monitor stopped by user[/bold yellow]")
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}", style="red")
    finally:
        # Cancel keyboard task
        keyboard_task.cancel()
        
        # Cancel all running tasks when exiting
        for task in tasks:
            task.cancel()
        
        # Wait for all tasks to be cancelled
        await asyncio.gather(*tasks, return_exceptions=True)

if __name__ == "__main__":
    try:
        console.print("\n[bold cyan]Starting Teneo WebSocket Monitor...[/bold cyan]")
        console.print("\n[bold yellow]Use LEFT/RIGHT arrow keys to navigate between token pages[/bold yellow]")
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n[bold yellow]Monitor stopped by user[/bold yellow]")
    except Exception as e:
        console.print(f"\n[bold red]Error:[/bold red] {str(e)}", style="red")
