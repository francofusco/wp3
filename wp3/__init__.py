from .firmware import download_pico_firmware
from .mpl import (
    add_tiles_to_axes,
    tight_figure,
    toggle_tile_if_clicked,
    toggle_all_tiles,
    wait_for_exit,
)
from .optimization import Routing, named_tree_search
from .settings import (
    load_materials,
    open_project,
    SettingsDict,
    update_cached_routing,
    update_initial_tiling,
)
from .struct import Struct
from .tile import (
    Tile,
    unique_vertices,
    create_vertices_map,
    count_vertices_repetitions,
    get_bounding_box,
    get_bounding_box_size,
    get_bounding_box_area,
)
from .tiles import *
import numpy as np


class BillItem(object):
    """Simple structure that represents items to purchase."""

    @staticmethod
    def dump_to_markdown(items, file_name):
        """Write a list of items (sorted by category) into a markdown table.

        Args:
            items: list containing BillItem instances.
            file_name: path of the csv file to be created.
        """
        with open(file_name, "w") as f:
            print("| Name | Quantity | Price | Category | Notes |", file=f)
            print("| --- | --- | --- | --- | --- |", file=f)
            total_cost = 0
            for item in sorted(items, key=lambda it: it.category):
                total_cost += item.quantity * item.cost
                print(
                    f"| {item.name} | {item.quantity} |"
                    f" {np.round(item.cost, 2)} | {item.category} |"
                    f" {item.notes} |",
                    file=f,
                )
            print(f"| Total |  | {np.round(total_cost, 2)} |  |  |", file=f)

    def __init__(self, name=None, quantity=1, cost=0, category="", notes=""):
        if name is None:
            raise ValueError("BillItem's name must be specified.")
        if "|" in name or "|" in category or "|" in notes:
            raise ValueError(
                "Commas cannot be specified in any of the filelds of ."
            )
        self.name = name
        self.quantity = quantity
        self.cost = cost
        self.category = category
        self.notes = notes
