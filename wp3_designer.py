import json
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib import colormaps
import numpy as np
import pathlib
import shutil
import sys
import time
import traceback
import wp3

# Remove interaction buttons to prevent the user change the canvas accidentally.
mpl.rcParams['toolbar'] = 'None'


def main():
    # Get configuration file and working directory.
    output_dir, settings = wp3.open_project()

    # Extract a list of materials.
    materials_list = wp3.load_materials(settings)

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
    fig, ax = wp3.tight_figure(tiles)

    # Place the tiles in the plot.
    wp3.add_tiles_to_axes(tiles, ax)

    # For each tile, create an event connection that toggles its visibility if
    # one clicks inside its patch.
    for tile in tiles:
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
        plt.pause(0.05)

    # Collect all tiles (and their coordinates) in the chosen design.
    visible_tiles = []
    tiling_coordinates = []
    for tile in tiles:
        if tile.is_visible():
            visible_tiles.append(tile)
            tiling_coordinates.append([tile.row, tile.col])

    # Store the current design in the YAML configuration file.
    wp3.update_initial_tiling(output_dir, settings, tiling_coordinates)

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
        fig, ax = wp3.tight_figure(visible_tiles)

        # Add visible tiles to the created Axis instance.
        wp3.add_tiles_to_axes(visible_tiles, ax, copy=True, patch_color="white",
                              border_color="lightgray")

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
            plt.pause(0.05)

        # Save the current routing into a figure, to make sure that it is safely
        # stored somewhere.
        fig.savefig(output_dir.joinpath("wp3_routing.pdf"), bbox_inches='tight', dpi=500)
        plt.close("all")

        # Decide what to do depending on the user's choice.
        if exit_helper.reroute:
            # Read routing parameters from the YAML configuration.
            routing_kwargs = settings.extract("routing", {})

            # Remove parameters that are not to be passed to Routing.optimize.
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
            # Routing completed!
            break

    # Store current routing.
    wp3.update_cached_routing(output_dir, settings, best_routing.tolist())

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

    # Write down how many walls of each type should be printed, with their
    # dimensions as well.
    walls_notes = f"Side Length: {np.round(1000*settings['panels']['side_length'], 2)}mm. Spacing: {np.round(1000*settings['panels']['spacing'], 2)}mm. Junction Angle: {np.round(180/walls_per_tile, 2)}deg. Remember to update the CAD accordingly and export the STL meshes to print them."
    bill_of_materials.append(wp3.BillItem(name="outer wall", quantity=outer_walls, category="3D printed", notes=walls_notes))
    bill_of_materials.append(wp3.BillItem(name="inner wall", quantity=inner_walls, category="3D printed", notes=walls_notes))

    # Process panel materials. The goal is, for each panel type, to evaluate how
    # many tiles can be inserted, or how much it costs to fill them (in case the
    # cost depends on the size).
    # TODO: it would be ideal to allow, for variable size materials, to let
    # the designer try with different sizes as well.
    panel_material_data = {}

    # Generated tiling files for all materials should be first saved into a
    # temporary file and then copied if needed.
    tiling_temp_dir = output_dir.joinpath("tiling_temp")
    tiling_temp_dir.mkdir(exist_ok=True)

    for (layer_name, layer) in materials_list["sheets"].items():
        # Get the size of the current sheet.
        width, height = layer["size"]

        # Try to fill the given sheet with all possible variants of the same
        # tile family.
        tilings = []
        for variant in TileClass.get_variants():
            tiling = TileClass.fit_in_sheet(len(visible_tiles), 0,
                                            settings["panels"]["side_length"],
                                            variant, width, height)
            if len(tiling) > 0:
                tilings.append(tiling)

        # If no tiling was possible, just skip this sheet.
        if len(tilings) == 0:
            print("Could not fit any tile in", layer_name)
            continue

        # Choose the best tiling variant. If the sheet has variable height,
        # the best variant is the one that minimizes the height of the sheet
        # itself. If the size is fixed, the best variant is the one that uses
        # the least amount of material per sheet. In both cases, evaluate the
        # height of the sheet and its cost.
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

        # Store the details of this sheet for the cost optimization, performed
        # later in the script.
        panel_material_data[layer_name] = wp3.Struct(name=layer_name,
                                                     value=len(tiles_layer),
                                                     cost=layer_cost,
                                                     variable_size=height==np.inf,
                                                     height=bb_height,
                                                     unit_cost=layer.get("cost", 0))

        # The figure is used to show how tiles should be cut from each sheet.
        fig, ax = plt.subplots()
        ax.set_aspect("equal")
        ax.set_xlim(0, width)
        ax.set_ylim(0, bb_height)
        ax.set_title(layer_name)
        fig.tight_layout()

        # Change the visual properties of the patches edges.
        for tile in tiles_layer:
            tile.patch.set_linewidth(0.2)
            tile.patch.set_edgecolor("black")

        # Add the patches to the fgure.
        wp3.add_tiles_to_axes(tiles_layer, ax, patch_color="lightgray")

        # Save the tiling into a file.
        fig.savefig(tiling_temp_dir.joinpath(f"tiling_{layer_name}.pdf"), bbox_inches='tight')
        plt.close("all")

    if settings.has("assembly", "sheets"):
        # For each group of materials that can be used to manufacture the tiles,
        # evaluate the cheapest combination of articles that can be purchased.
        for i, materials in enumerate(settings["assembly"]["sheets"]):
            # Get the list of sheets that have to be purchased, and their quantity.
            components, cost, _ = wp3.named_tree_search([panel_material_data[m] for m in materials], len(visible_tiles))

            # For each sheet type to be purchased, add a line in the bill of
            # materials that specifies how many sheets to buy (or their length in
            # the case of variable-length sheets).
            for component, quantity in components:
                url = materials_list["sheets"][component.name].get("url")
                url_md = f"[url link]({url})" if url is not None else ""
                if component.variable_size:
                    quantity = np.round(component.height, 3)
                bill_of_materials.append(wp3.BillItem(name=component.name, quantity=quantity, cost=component.unit_cost, category=f"sheets-{i}", notes=url_md))

                shutil.copy(tiling_temp_dir.joinpath(f"tiling_{component.name}.pdf"), output_dir)
    shutil.rmtree(tiling_temp_dir)

    if settings.has("assembly", "leds"):
        # Process LED materials: evaluate how many LED strips have to be purchased.
        for i, materials in enumerate(settings["assembly"]["leds"]):
            # Make sure that the list of strips is not empty.
            if len(materials) == 0:
                print(f"Error in assembly list 'leds/{i}': no materials specified.")
                return

            # Check if all strips in this assembly have the same LED density.
            led_density = materials_list["leds"][materials[0]]["leds_per_meter"]
            for m in materials[:1]:
                if materials_list["leds"][m]["leds_per_meter"] != led_density:
                    print(f"Error in assembly list 'leds/{i}'. The components "
                          f"'{materials[0]}' and '{m}' have a different amount of "
                          f"LEDs per meter.")
                    return

            # Evaluate how many LEDs should be inserted in a single strip and how
            # many meters would be needed to have all tiles filled with LEDs.
            leds_per_tile_float = visible_tiles[0].perimeter() * led_density
            if np.allclose(np.round(leds_per_tile_float), leds_per_tile_float):
                leds_per_tile = np.round(leds_per_tile_float).astype(int)
            else:
                leds_per_tile = np.floor(visible_tiles[0].perimeter() * led_density).astype(int)
            required_led_length = len(visible_tiles) * leds_per_tile / led_density

            # Get the list of strips that have to be purchased, and their quantity.
            components, cost, _ = wp3.named_tree_search([wp3.Struct(name=m,
                value=materials_list["leds"][m]["number_of_leds"] / materials_list["leds"][m]["leds_per_meter"],
                cost=materials_list["leds"][m].get("cost", 0))
                for m in materials], required_led_length)

            # For each strip type to be purchased, add a line in the bill of
            # materials that specifies how many to buy.
            for component, quantity in components:
                led_notes = f"Leds per tile: {leds_per_tile}."
                url = materials_list["leds"][component.name].get("url")
                if url is not None:
                    led_notes += f" [url link]({url})"
                bill_of_materials.append(wp3.BillItem(name=component.name, quantity=quantity, cost=component.cost, category=f"leds-{i}", notes=led_notes))

            # If wattage information is provided for all strips, try to estimate the
            # total wattage required to power the LEDs and add this information to
            # the bill of materials (as a PSU item).
            watts = sum(n*materials_list["leds"][c.name].get("watts", np.nan) for c, n in components)
            if watts != np.nan:
                bill_of_materials.append(wp3.BillItem(name=f"{watts}W Power Supply Unit", category=f"leds-{i}", notes="The power has been estimated. You might need a lower wattage."))

            # Knowing the number of LEDs per tile, we can provide a detailed scheme
            # of the wiring. This information is stored in a PDF document that can
            # be viewed by the user.
            fig, ax = wp3.tight_figure(visible_tiles)
            wp3.add_tiles_to_axes(visible_tiles, ax, copy=True, patch_color="white",
                                  border_color="lightgray")
            routing.plot_detailed_routing(best_routing, visible_tiles, leds_per_tile, ax)
            fig.savefig(output_dir.joinpath(f"wp3_routing_{leds_per_tile}_leds_per_tile.pdf"), bbox_inches='tight', dpi=500)
            plt.close("all")

            # Generate a component file for SignalRGB. The component in the
            # "Layouts" page will be a rectangle with maximum dimenions equal to
            # 100 - an arbitrary number that seems reasonable on my PC.
            width, height = wp3.get_bounding_box_size(visible_tiles)
            scale = 100 / max(width, height)
            width *= scale
            height *= scale
            dev_name = f"WP3 {output_dir.name}"
            signal_rgb_data = {
                "ProductName": dev_name,
                "DisplayName": dev_name,
                "Brand": "WP3",
                "Type": "custom",
                "LedCount": int(len(visible_tiles) * leds_per_tile),
                "Width": int(width),
                "Height": int(height),
                "LedMapping": [],
                "LedCoordinates": [],
                "LedNames": []
            }

            # Get the origin of the bounding box, to properly shift LEDs towards the
            # bottom-left corner.
            origin, _ = wp3.get_bounding_box(visible_tiles)

            # Store, for each LED in the routing path, its name and coordinates.
            for segment in routing.get_detailed_routing_points(best_routing, visible_tiles, leds_per_tile):
                for led in segment:
                    led_idx = len(signal_rgb_data["LedMapping"])
                    signal_rgb_data["LedMapping"].append(led_idx)
                    led_coordinates = (led-origin)*scale
                    led_coordinates[1] = height - led_coordinates[1]
                    signal_rgb_data["LedCoordinates"].append(np.round(led_coordinates).astype(int).tolist())
                    signal_rgb_data["LedNames"].append(f"Led {led_idx} (tile {led_idx//leds_per_tile})")

            # Save the generated data into a JSON file that can be imported into
            # SignalRGB to define the custom LED geometry.
            with open(output_dir.joinpath(f"wp3_{output_dir.name}_{leds_per_tile}_leds_signal_rgb.json"), "w") as f:
                json.dump(signal_rgb_data, f)

    # Add to the bill of materials one entry that corresponds to the number of
    # connectors to be purchased.
    bill_of_materials.append(wp3.BillItem(name="3 pin connectors", quantity=len(visible_tiles), category="wiring", notes="The quantity refers to male/female pairs."))

    # Print the bill of materials into a file.
    wp3.BillItem.dump_to_markdown(bill_of_materials, output_dir.joinpath("bill_of_materials.md"))

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        if not isinstance(e, SystemExit):
            traceback.print_exc()
            print("---------------------------------------------------")
            print("Execution stopped unexpectedly.")
            print("Consider opening an issue at:")
            print("  https://github.com/francofusco/wp3/issues/new")
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            print("Press CTRL+C to exit, or close the terminal window.")
            try:
                while True:
                    pass
            except KeyboardInterrupt:
                pass
