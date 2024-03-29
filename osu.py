import os
import sys
import threading

import gi
import requests

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib, Pango
from github import Github

g = Github(None)
repo = g.get_repo("ppy/osu")

def get_script_name():
    if getattr(sys, 'frozen', False):
        # Running in PyInstaller bundle
        return os.path.basename(f"{sys.argv[0]}")
    else:
        # Running as a standalone script
        return os.path.basename(__file__)

class Updater(Gtk.Window):
    def __init__(self):
        super().__init__(title="osu! updater")
        self.set_border_width(10)

        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)

        self.progressbar = Gtk.ProgressBar()
        
        self.set_default_size(300, 400)
        self.set_resizable(False)

        self.cookie = Gtk.Image.new_from_file(os.path.join(os.getcwd(), "assets/cookie.png"))

        self.update_greet = Gtk.Label(label="Hi!")
        self.update_greet.modify_font(Pango.FontDescription("Sans 24"))

        self.update_label = Gtk.Label(label="Your game client is being updated")

        version = None
        version_file_path = os.path.join(os.getcwd(), "version.txt")
        if os.path.isfile(version_file_path):
            with open(version_file_path, "r") as version_file:
                version = version_file.readline().strip()

        self.version_label = Gtk.Label(label=f"[{version if version else 'Installing'}] -> [{repo.get_releases()[0].title}]")
        self.changelog_button = Gtk.LinkButton(uri=f"https://osu.ppy.sh/home/changelog/lazer/{repo.get_releases()[0].title}", label="Changelog")
        
        self.box.pack_start(self.cookie, True, True, 0)
        self.box.pack_start(self.update_greet, False, False, 0)
        self.box.pack_start(self.update_label, False, False, 0)
        self.box.pack_start(self.progressbar, True, True, 0)
        self.box.pack_start(self.version_label, False, False, 0)
        self.box.pack_start(self.changelog_button, False, False, 0)
        
        self.add(self.box)

        self.timeout_id = None

    def start_download(self):
        threading.Thread(target=self.download_thread).start()

    def download_thread(self):
        try:
            release = None
            for asset in repo.get_releases()[0].assets:
                if asset.name.lower().endswith(".appimage"):
                    release = asset
                    break
            
            if release is None:
                raise ValueError("No AppImage found in the release assets.")
            
            
            with requests.Session() as session:
                response = session.get(release.browser_download_url, stream=True)
                response.raise_for_status()  # Raise exception for HTTP errors

                total_length = int(response.headers.get('content-length'))
                bytes_received = 0

                download_path = os.path.join(os.getcwd(), "osu.AppImage")
                with open(download_path, "wb") as file:
                    chunk_size = 1024
                    for data in response.iter_content(chunk_size=chunk_size):
                        file.write(data)
                        bytes_received += len(data)
                        fraction = bytes_received / total_length
                        GLib.idle_add(self.update_progress, fraction)
                    
                    os.chmod(download_path, 0o755)  # Change file mode
                    desktop_file_path = os.path.expanduser("~/.local/share/applications/osu.desktop")
                    with open(desktop_file_path, "w") as desktop_file:
                        desktop_file.write("[Desktop Entry]\n")
                        desktop_file.write("Type=Application\n")
                        desktop_file.write("Version=1.0\n")
                        desktop_file.write("Name=osu!\n")
                        desktop_file.write("Comment=Rhythm is just a *click* away\n")
                        desktop_file.write(f"Path={os.getcwd()}\n")
                        script_name = "./" + get_script_name().replace(" ", "\ ") #This is a workaround to allow the executable to have a goofy filename
                        desktop_file.write(f"Exec={'./osu.sh' if script_name.endswith('.py') else script_name}\n")
                        desktop_file.write(f"Icon={os.path.join(os.getcwd(), 'assets/cookie.png')}\n")
                        desktop_file.write("Terminal=false\n")
                
                with open(os.path.join(os.getcwd(), "version.txt"), "w") as version_file:
                    version_file.write(f"{repo.get_releases()[0].title}")
                
                # Close the updater window
                GLib.idle_add(self.destroy)
        except requests.exceptions.RequestException as e:
            GLib.idle_add(self.show_error_message, str(e))
        except Exception as e:
            GLib.idle_add(self.show_error_message, str(e))

    def update_progress(self, fraction):
        self.progressbar.set_fraction(fraction)
        if fraction >= 1:
            self.progressbar.set_text("Download Complete")

    def show_error_message(self, message):
        dialog = Gtk.MessageDialog(parent=self, flags=0, message_type=Gtk.MessageType.ERROR, buttons=Gtk.ButtonsType.OK, text=message)
        dialog.run()
        dialog.destroy()

    def run(self):
        self.connect("destroy", Gtk.main_quit)
        self.show_all()
        Gtk.main()

if __name__ == "__main__":
    version_file_path = os.path.join(os.getcwd(), "version.txt")
    if os.path.isfile(version_file_path) and os.path.isfile(os.path.join(os.getcwd(), "osu.AppImage")):
        with open(version_file_path, "r") as version_file:
            version = version_file.readline().strip()
    else:
        version = None

    if version != repo.get_releases()[0].title:
        updater = Updater()
        updater.start_download()
        updater.run()
    os.system(os.path.join(os.getcwd(), "osu.AppImage"))
