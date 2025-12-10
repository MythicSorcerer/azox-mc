# FILE: mcplayer.py (main)
"""
Entrypoint that composes panels into the Textual App and wires events.
"""
from textual.app import App
from textual.containers import Horizontal, Container, Grid
from textual.widgets import Header, Footer
from panels import PlayerListPanel, InfoPanel, InventoryPanel, EnderPanel, ArmorPanel, AttributesPanel, PosPanel, RawNbtPanel, PlayerSelected, CopyInventoryRequest
from nbtcore import list_players, read_nbt, safe_root, save_nbt

class McEditorApp(App):
    CSS_PATH = None

    def compose(self):
        yield Header()
        with Horizontal():
            with Container(id='left'):
                self.players = PlayerListPanel()
                yield self.players
            with Container(id='right'):
                self.info = InfoPanel()
                yield self.info
                with Grid():
                    self.inventory = InventoryPanel()
                    self.ender = EnderPanel()
                    self.armor = ArmorPanel()
                    self.attrs = AttributesPanel()
                    self.pos = PosPanel()
                    self.raw = RawNbtPanel()
                    yield self.inventory
                    yield self.ender
                    yield self.armor
                    yield self.attrs
                    yield self.pos
                    yield self.raw
        yield Footer()

    async def handle_player_selected(self, message: PlayerSelected) -> None:
        uuid = message.uuid; name = message.name; path = message.path
        try:
            nbt_file = read_nbt(path); root = safe_root(nbt_file)
        except Exception as e:
            await self.notify(f"Failed to load: {e}")
            return
        # set into info and panels
        self.info.set_player(uuid, name, path)
        self.inventory.load_root(root)
        self.ender.load_root(root)
        self.armor.load_root(root)
        self.attrs.load_root(root)
        self.pos.load_root(root)
        self.raw.load_root(root)

    async def handle_copyinventoryrequest(self, message: CopyInventoryRequest) -> None:
        # delegate to info panel by posting a message
        pass

    async def prompt(self, message: str):
        # simple blocking prompt via run_in_thread
        return await self.run_in_thread(lambda: input(message + ' '))

    async def notify(self, message: str):
        # brief notifications printed to footer
        self.query_one(Footer).update(message)


def main():
    app = McEditorApp()
    app.run()

if __name__ == '__main__':
    main()

# Starting from the beginning; will include entire file.
