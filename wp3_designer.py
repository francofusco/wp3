import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib import colormaps
import numpy as np
import pathlib
import time
import wp3

# Remove interaction buttons to prevent the user change the canvas accidentally.
mpl.rcParams['toolbar'] = 'None'


def main():
    # Get configuration file and working directory.
    config_file = pathlib.Path(wp3.retrieve_settings_file())
    output_dir = config_file.parent.joinpath("design_info")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load settings from a YAML file.
    settings = wp3.load_settings(config_file)

    # Load type and variant of the tile.
    tile_type_specs = settings["panels"]["type"].split("#") + [0]

    # Check if the type is a valid symbol in wp3.
    if not hasattr(wp3, tile_type_specs[0]):
        print(f"The panels type '{tile_type_specs[0]}' does not exist. Please, check your YAML configuration file.")
        return

    # Get the type and check if it is a Tile subclass.
    TileClass = getattr(wp3, tile_type_specs[0])
    if not isinstance(TileClass, type) or not issubclass(TileClass, wp3.Tile):
        print(f"The panels type '{tile_type_specs[0]}' is not a Tile subclass. Please, check your YAML configuration file.")
        return

    # Get the variant of the panels and check that it is valid.
    tile_variant = int(tile_type_specs[1])
    if tile_variant not in TileClass.get_variants():
        print(f"The panels variant '{tile_variant}' is invalid; valid variants for '{tile_type_specs[0]}' are: {', '.join(map(str, TileClass.get_variants()))}. Please, check your YAML configuration file.")
        return

    # Load a design from the settings, if this is available.
    initial_tiling = settings["panels"].get("initial_tiling")

    # Fill the available design space with the chosen tiles.
    tiles = []
    for row in range(settings["panels"]["rows"]):
        for col in range(settings["panels"]["columns"]):
            tile = TileClass(row, col, settings["panels"]["spacing"],
                             settings["panels"]["side_length"], tile_variant)
            tiles.append(tile)
            # If an initial design is provided and this tile is not part of it,
            # make sure to hide it.
            if initial_tiling is not None and [row, col] not in initial_tiling:
                tile.set_visible(False)

    # Calculate the dimensions of the canvas.
    canvas_width, canvas_height = wp3.get_bounding_box_size(tiles)

    # Create a figure to plot the tiles.
    fig, ax = plt.subplots()
    ax.set_aspect("equal")
    ax.set_xlim(0, canvas_width)
    ax.set_ylim(0, canvas_height)
    ax.tick_params(which="both", bottom=False, top=False, right=False,
                   left=False, labelbottom=False, labelleft=False)
    ax.set_axisbelow(True)
    fig.tight_layout()

    # Place the tiles in the plot.
    for tile in tiles:
        # Add the current tile to the canvas, and create an event connection
        # that toggles its visibility if one clicks inside its patch.
        tile.add_to_axis(ax)
        fig.canvas.mpl_connect('button_press_event', lambda event, tile=tile: wp3.toggle_tile_if_clicked(event, tile, ax))

    # Create a connection to hide, show or toggle all tile visibilities at once
    # using the keyboard.
    fig.canvas.mpl_connect('key_press_event', lambda event: wp3.toggle_all_tiles(event, tiles, ax))

    # Detect when a figure is closed using an event connection.
    exit_helper = wp3.Struct(keep_running = True)
    fig.canvas.mpl_connect('close_event', lambda event: setattr(exit_helper, "keep_running", False))

    # Period and shift factor to color all tiles using a HSV wave.
    period = 4.0
    velocity = 0.005

    # Loop that changes the color of each tile and then updates the plot.
    # The loop will stop once the figure is closed.
    while exit_helper.keep_running:
        for i, tile in enumerate(tiles):
            tile.patch.set_color(colormaps["hsv"](((time.time() / period - i * velocity) % 1)))
        plt.pause(0.001)

    # Collect all tiles (and their coordinates) in the chosen design.
    visible_tiles = []
    tiling_coordinates = []
    for tile in tiles:
        if tile.is_visible():
            visible_tiles.append(tile)
            tiling_coordinates.append([tile.row, tile.col])
    with open(output_dir.joinpath("initial_tiling.yaml"), "a") as f:
        print("initial_tiling:", tiling_coordinates, file=f)

    # Read how many segments should be generated in the routing problem.
    segments = 1
    if settings.has("routing", "segments") and settings.has("routing", "tiles_per_segment"):
        print("Sorry, but the parameters 'routing/segments' and "
              "'routing/tiles_per_segment' should not be given at the same time")
    if settings.has("routing", "segments"):
        segments = settings["routing"]["segments"]
    elif settings.has("routing", "tiles_per_segment"):
        segments = np.ceil(len(visible_tiles) / settings["routing"]["tiles_per_segment"]).astype(int)

    # Setup the routing problem and generate an initial solution, either from
    # a pre-computed one or at random.
    routing = wp3.Routing(visible_tiles, segments=segments)
    best_routing = routing.random_sample()
    if settings.has("routing", "cache"):
        cache = np.array(settings["routing"]["cache"])
        if cache.shape == best_routing.shape and cache[1].max() < routing.vertices_per_tile:
            best_routing = cache

    # Optimize cable connections (routing). This is done in a loop that roughly
    # looks like:
    # 1. Show current routing in a figure;
    # 2. If the user presses the space bar:
    #    - Close the figure;
    #    - Improve the solution;
    #    - Go back to 1;
    # 3. If the user closes the routing window: exit.
    while True:
        # Create a figure to plot the tiles.
        fig, ax = plt.subplots()
        ax.set_aspect("equal")
        (xmin, ymin), (xmax, ymax) = wp3.get_bounding_box(visible_tiles)
        ax.set_xlim(xmin, xmax)
        ax.set_ylim(ymin, ymax)
        ax.tick_params(which="both", bottom=False, top=False, right=False,
                       left=False, labelbottom=False, labelleft=False)
        ax.set_axisbelow(True)
        fig.tight_layout()

        # Add visible tiles to the created Axis instance.
        for tile in visible_tiles:
            tile = tile.make_copy()
            tile.add_to_axis(ax)
            tile.patch.set_color("white")
            tile.outer_patch.set_color("lightgray")

        # Save the content of the figure so that one can try to manually draw a
        # routing if needed.
        fig.savefig(output_dir.joinpath("wp3_design.pdf"), bbox_inches='tight')

        # Add the proposed routing to the Axis.
        routing.plot_routing(best_routing, visible_tiles, ax)

        # Establish connections to be able to detect when the user presses the
        # space bar or closes the figure.
        exit_helper = wp3.Struct(keep_running=True, reroute=False)
        fig.canvas.mpl_connect('key_press_event', lambda event: setattr(exit_helper, "reroute", event.key == " "))
        fig.canvas.mpl_connect('close_event', lambda event: setattr(exit_helper, "keep_running", False))

        # Loop that waits for user interaction.
        while exit_helper.keep_running and not exit_helper.reroute:
            plt.pause(0.001)

        # Save the current routing into a figure, to make sure that it is safely
        # stored somewhere.
        fig.savefig(output_dir.joinpath("wp3_routing.pdf"), bbox_inches='tight')
        plt.close("all")

        # Decide what to do depending on the user's choice.
        if exit_helper.reroute:
            # Read routing parameters from the YAML configuration.
            routing_kwargs = settings.extract("routing", {})
            if "cache" in routing_kwargs:
                routing_kwargs.pop("cache")
            if "segments" in routing_kwargs:
                routing_kwargs.pop("segments")
            if "tiles_per_segment" in routing_kwargs:
                routing_kwargs.pop("tiles_per_segment")

            # Try to improve the routing path.
            routing_cost_before = routing.evaluate_cost(best_routing)
            best_routing = routing.optimize(best_sample=best_routing, **routing_kwargs)
            routing_cost_after = routing.evaluate_cost(best_routing)
            print("Cost decreased by", np.round(100 * (routing_cost_before-routing_cost_after) / routing_cost_before, 3))
        else:
            break

    with open(output_dir.joinpath("routing_cache.yaml"), "a") as f:
        print("cache:", best_routing.tolist(), file=f)

    # List of items to be purchased/manufactured.
    bill_of_materials = []

    # Count how many "walls" are needed. If all tiles were separated, we would
    # have a total of six outer walls per tile. However, whenever two tiles
    # share a side, the corresponding two outer walls should be replaced by a
    # single inner wall.
    walls_per_tile = len(visible_tiles[0].vertices())
    outer_walls = len(visible_tiles) * walls_per_tile
    inner_walls = 0
    # Look for all pairs of tiles, with no repetitions.
    for i, tile in enumerate(visible_tiles):
        for other in visible_tiles[i+1:]:
            # If the other tile is adjacent, then remove one shared wall.
            if tile.adjacent(other):
                outer_walls -= 2
                inner_walls += 1
    walls_notes = f"Side Length: {np.round(1000*settings['panels']['side_length'], 2)}mm. Spacing: {np.round(1000*settings['panels']['spacing'], 2)}mm. Junction Angle: {np.round(180/walls_per_tile, 2)}deg. Remember to update the CAD accordingly and export the STL meshes to print them."
    bill_of_materials.append(wp3.BillItem(name="outer wall", quantity=outer_walls, category="3D printed", notes=walls_notes))
    bill_of_materials.append(wp3.BillItem(name="inner wall", quantity=inner_walls, category="3D printed", notes=walls_notes))

    # Process panel materials. The goal is, for each panel type, to evaluate how
    # many tiles can be inserted, or how much it costs to fill them (in case the
    # cost depends on the size).
    # TODO: it would be ideal to allow, for variable size materials, to let
    # the designer try with different sizes as well.
    panel_material_data = {}

    for i, (layer_name, layer) in enumerate(settings["materials"]["sheets"].items()):
        fig, ax = plt.subplots()
        width, height = layer["size"]
        tilings = []
        for variant in TileClass.get_variants():
            tiling = TileClass.fit_in_sheet(len(visible_tiles), 0,
                                            settings["panels"]["side_length"],
                                            variant, width, height)
            if len(tiling) > 0:
                tilings.append(tiling)
        if len(tilings) == 0:
            print("Could not fit any tile in", layer_name)
            continue

        if height == np.inf:
            heights = np.array([wp3.get_bounding_box_size(tiling)[1] for tiling in tilings])
            idx = heights.argmin()
            bb_height = heights[idx]
            tiles_layer = tilings[idx]
            layer_cost = layer.get("cost", 0) * bb_height
        else:
            areas = np.array([wp3.get_bounding_box_area(tiling) for tiling in tilings])
            tiles_layer = tilings[areas.argmin()]
            layer_cost = layer.get("cost", 0)
            bb_height = height

        panel_material_data[layer_name] = wp3.Struct(name=layer_name,
                                                     value=len(tiles_layer),
                                                     cost=layer_cost,
                                                     variable_size=height==np.inf,
                                                     height=bb_height,
                                                     unit_cost=layer.get("cost", 0))

        ax.set_aspect("equal")
        ax.set_xlim(0, width)
        ax.set_ylim(0, bb_height)
        ax.set_title(layer_name)

        for tile in tiles_layer:
            tile.patch.set_linewidth(0.2)
            tile.patch.set_edgecolor("black")
            tile.patch.set_facecolor("lightgray")
            tile.add_to_axis(ax)

        fig.tight_layout()
        fig.savefig(output_dir.joinpath(f"{layer_name}.pdf"), bbox_inches='tight')
        plt.close("all")

    for i, materials in enumerate(settings["assembly"]["sheets"]):
        components, cost, value = wp3.named_tree_search([panel_material_data[m] for m in materials], len(visible_tiles))
        for component, quantity in components:
            url = settings["materials"]["sheets"][component.name].get("url")
            url_md = f"[url link]({url})" if url is not None else ""
            if component.variable_size:
                quantity = np.round(component.height, 3)
            bill_of_materials.append(wp3.BillItem(name=component.name, quantity=quantity, cost=component.unit_cost, category=f"sheets-{i}", notes=url_md))

    required_led_length = len(visible_tiles) * walls_per_tile * settings["panels"]["side_length"]
    for i, materials in enumerate(settings["assembly"]["leds"]):
        error_message_base = f"Error in assembly list 'leds/{i}'."
        led_density = settings["materials"]["leds"][materials[0]]["leds_per_meter"]
        for m in materials[:1]:
            if settings["materials"]["leds"][m]["leds_per_meter"] != led_density:
                print(f"Error in assembly list 'leds/{i}'. The components "
                      f"'{materials[0]}' and '{m}' have a different amount of "
                      f"LEDs per meter.")
                return

        components, cost, value = wp3.named_tree_search([wp3.Struct(name=m,
            value=settings["materials"]["leds"][m]["number_of_leds"] / settings["materials"]["leds"][m]["leds_per_meter"],
            cost=settings["materials"]["leds"][m].get("cost", 0))
            for m in materials], required_led_length)
        for component, quantity in components:
            url = settings["materials"]["leds"][component.name].get("url")
            url_md = f"[url link]({url})" if url is not None else ""
            bill_of_materials.append(wp3.BillItem(name=component.name, quantity=quantity, cost=component.cost, category=f"leds-{i}", notes=url_md))
        watts = sum(n*settings["materials"]["leds"][c.name].get("watts", np.nan) for c, n in components)
        if watts != np.nan:
            bill_of_materials.append(wp3.BillItem(name=f"{watts}W Power Supply Unit", category=f"leds-{i}", notes="The power has been estimated. You might need a lower wattage."))

    bill_of_materials.append(wp3.BillItem(name="3 pin connectors", quantity=len(visible_tiles), category="wiring", notes="The quantity refers to male/female pairs."))
    bill_of_materials.append(wp3.BillItem(name="Three-way electrical wire", quantity=np.round(routing.evaluate_cost(best_routing, repetition_penalty=0), 3), category="wiring", notes="This is likely an overestimation, since the length of the connectors is not taken into account."))

    wp3.BillItem.dump_to_markdown(bill_of_materials, output_dir.joinpath("bill_of_materials.md"))

if __name__ == '__main__':
    main()
