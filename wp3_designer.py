import argparse
import json
import logging
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib import colormaps
import numpy as np
import pathlib
import shutil
import sys
import textwrap
import time
import traceback
import wp3

# Remove interaction buttons to prevent the user change the canvas accidentally.
mpl.rcParams['toolbar'] = 'None'

logger = logging.getLogger("wp3_designer")


def main():
    # Get configuration file and working directory.
    output_dir, settings = wp3.open_project()
    logger.info(f"Working on project '{output_dir.name}'.")

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
    logger.info("Loaded initial tiling from 'config.yaml'." if initial_tiling
                is not None else "No initial tiling found in loaded settings.")

    # Fill the available design space with the chosen tiles.
    tiles = []
    for row in range(settings["panels"]["rows"]):
        for col in range(settings["panels"]["columns"]):
            tile = TileClass(row, col, settings["panels"]["spacing"],
                             settings["panels"]["side_length"], tile_variant)
            tiles.append(tile)
            logger.debug(f"Added new tile in (row, col) = ({row}, {col}). "
                         f"Cartesian coordinates: ({tile.x}, {tile.y}).")
            # If an initial design is provided and this tile is not part of it,
            # make sure to hide it.
            if initial_tiling is not None and [row, col] not in initial_tiling:
                logger.debug("Hiding this tile as it is not part of the "
                             "initial tiling.")
                tile.set_visible(False)

    # Calculate the dimensions of the canvas.
    canvas_width, canvas_height = wp3.get_bounding_box_size(tiles)
    logger.debug(f"Canva's dimensions: {canvas_width} by {canvas_height}.")

    # Create a figure to plot the tiles.
    fig, ax = wp3.tight_figure(tiles)

    # Place the tiles in the plot.
    wp3.add_tiles_to_axes(tiles, ax)

    # For each tile, create an event connection that toggles its visibility if
    # one clicks inside its patch.
    for tile in tiles:
        logger.debug(f"Creating mpl connection for tile ({tile.row}, "
                     f"{tile.col}).")
        fig.canvas.mpl_connect("button_press_event", lambda event, tile=tile: wp3.toggle_tile_if_clicked(event, tile, ax))

    # Create a connection to hide, show or toggle all tile visibilities at once
    # using the keyboard.
    fig.canvas.mpl_connect("key_press_event", lambda event: wp3.toggle_all_tiles(event, tiles, ax))

    # Detect when a figure is closed using an event connection.
    exit_helper = wp3.Struct(keep_running = True)
    fig.canvas.mpl_connect("close_event", lambda event: setattr(exit_helper, "keep_running", False))

    # Period and shift factor to color all tiles using a HSV wave.
    period = 4.0
    velocity = 0.005

    # Loop that changes the color of each tile and then updates the plot.
    # The loop will stop once the figure is closed.
    logger.debug("Entering main loop to select the tiles.")
    while exit_helper.keep_running:
        for i, tile in enumerate(tiles):
            tile.patch.set_color(colormaps["hsv"](((time.time() / period - i * velocity) % 1)))
        plt.pause(0.05)
    logger.debug("Designer window was closed by the user.")

    # Collect all tiles (and their coordinates) in the chosen design.
    visible_tiles = []
    tiling_coordinates = []
    for tile in tiles:
        if tile.is_visible():
            visible_tiles.append(tile)
            tiling_coordinates.append([tile.row, tile.col])
    logger.debug(f"Initial tiling array (to be stored in 'config.yaml'): "
                 f"{tiling_coordinates}.")

    # Store the current design in the YAML configuration file.
    wp3.update_initial_tiling(output_dir, settings, tiling_coordinates)

    # Read how many segments should be generated in the routing problem.
    segments = 1
    if settings.has("routing", "segments") and settings.has("routing", "tiles_per_segment"):
        print("Sorry, but the parameters 'routing/segments' and "
              "'routing/tiles_per_segment' should not be given at the same "
              "time. Please, update 'config.yaml' and re-launch the designer.")
        return
    if settings.has("routing", "segments"):
        segments = settings["routing"]["segments"]
        logger.debug(f"Found parameter 'routing/segments'; value: {segments}.")
    elif settings.has("routing", "tiles_per_segment"):
        tiles_per_segment = settings["routing"]["tiles_per_segment"]
        segments = np.ceil(len(visible_tiles) / tiles_per_segment).astype(int)
        logger.debug(f"Found parameter 'routing/tiles_per_segment'; value: "
                     f"{tiles_per_segment}.")

    # Setup the routing problem and generate an initial solution, either from
    # a pre-computed one or at random.
    logger.debug(f"Creating routing problem with {segments} segments.")
    routing = wp3.Routing(visible_tiles, segments=segments)
    best_routing = routing.random_sample()
    if settings.has("routing", "cache"):
        cache = np.array(settings["routing"]["cache"])
        logger.debug(f"Loaded routing cache: {cache.tolist()}.")
        if cache.shape == best_routing.shape and cache[1].max() < routing.vertices_per_tile:
            best_routing = cache
        else:
            logger.info("Loaded routing cache is not compatible with the "
                        "current tiling. This might simply mean that routing "
                        "was previously performed on a different design.")

    # Read routing parameters from the YAML configuration.
    routing_kwargs = settings.extract("routing", {})

    # Remove parameters that are not to be passed to Routing.optimize.
    if "cache" in routing_kwargs:
        logger.debug("Removing parameter 'cache' from 'routing_kwargs'.")
        routing_kwargs.pop("cache")
    if "segments" in routing_kwargs:
        logger.debug("Removing parameter 'segments' from 'routing_kwargs'.")
        routing_kwargs.pop("segments")
    if "tiles_per_segment" in routing_kwargs:
        logger.debug("Removing parameter 'tiles_per_segment' from 'routing_kwargs'.")
        routing_kwargs.pop("tiles_per_segment")
    logger.debug(f"Routing keyword arguments: {routing_kwargs}.")

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
        design_file_name = output_dir.joinpath("wp3_design.pdf")
        logger.debug(f"Saving current design into '{design_file_name}'.")
        fig.savefig(design_file_name, bbox_inches='tight')

        # Add the proposed routing to the Axis.
        routing.plot_routing(best_routing, visible_tiles, ax)

        # Establish connections to be able to detect when the user presses the
        # space bar or closes the figure.
        logger.debug("Creating connections to detect when the user presses the "
                     "space bar or closes the figure.")
        exit_helper = wp3.Struct(keep_running=True, reroute=False)
        fig.canvas.mpl_connect('key_press_event', lambda event: setattr(exit_helper, "reroute", event.key == " "))
        fig.canvas.mpl_connect('close_event', lambda event: setattr(exit_helper, "keep_running", False))

        # Loop that waits for user interaction.
        logger.debug("Waiting for the user to press the space bar or close the "
                     "active figure.")
        while exit_helper.keep_running and not exit_helper.reroute:
            plt.pause(0.05)

        # Save the current routing into a figure, to make sure that it is safely
        # stored somewhere.
        routing_file_name = output_dir.joinpath("wp3_routing.pdf")
        logger.debug(f"Saving current routing into '{routing_file_name}'.")
        fig.savefig(routing_file_name, bbox_inches='tight', dpi=500)
        plt.close("all")

        # Decide what to do depending on the user's choice.
        if exit_helper.reroute:
            # Try to improve the routing path.
            logger.debug("Rerouting requested.")
            routing_cost_before = routing.evaluate_cost(best_routing)
            best_routing = routing.optimize(best_sample=best_routing, **routing_kwargs)
            routing_cost_after = routing.evaluate_cost(best_routing)
            print("Cost decreased by", np.round(100 * (routing_cost_before-routing_cost_after) / routing_cost_before, 3))
        else:
            # Routing completed!
            logger.debug("Figure closed: routing completed.")
            break

    logger.info(f"Design and routing files have been saved into "
                f"'{design_file_name}' and '{routing_file_name}'.")

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
    logger.info(f"Parts in the design: {len(visible_tiles)} tiles, "
                f"{outer_walls} outer walls, {inner_walls} inner walls.")

    # Write down how many walls of each type should be printed, with their
    # dimensions as well.
    logger.debug("Adding walls info to the bill of materials.")
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
    logger.debug(f"Creating temporary directory '{tiling_temp_dir}' to store "
                 f"temporary tiling files.")
    tiling_temp_dir.mkdir(exist_ok=True)

    for (layer_name, layer) in materials_list["sheets"].items():
        # Get the size of the current sheet.
        width, height = layer["size"]
        logger.debug(f"Processing material '{layer_name}' with dimensions "
                     f"{width}x{height}.")

        # Try to fill the given sheet with all possible variants of the same
        # tile family.
        tilings = []
        for variant in TileClass.get_variants():
            logger.debug(f"Tiling '{layer_name}' with variant {variant}.")
            tiling = TileClass.fit_in_sheet(len(visible_tiles), 0,
                                            settings["panels"]["side_length"],
                                            variant, width, height)
            logger.debug(f"Tiling completed, it contains {len(tiling)} tiles.")
            if len(tiling) > 0:
                tilings.append(tiling)

        # If no tiling was possible, just skip this sheet.
        if len(tilings) == 0:
            logger.warn(f"Could not fit any tile in {layer_name}.")
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
            logger.debug(f"The sheet '{layer_name}' had variable size. After "
                         f"tiling, the heights {heights} were calculated. The "
                         f"optimal one (#{idx}) has height {bb_height} and "
                         f"cost {layer_cost}.")
        else:
            areas = np.array([wp3.get_bounding_box_area(tiling) for tiling in tilings])
            idx = areas.argmin()
            tiles_layer = tilings[idx]
            layer_cost = layer.get("cost", 0)
            bb_height = height
            logger.debug(f"The sheet '{layer_name}' had fixed size. After "
                         f"tiling, the covered areas {areas} were calculated. "
                         f"The optimal one (#{idx}) has area {areas[idx]}.")

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

        # Add the patches to the figure.
        wp3.add_tiles_to_axes(tiles_layer, ax, patch_color="lightgray")

        # Save the tiling into a file.
        temp_tiling_file_name = tiling_temp_dir.joinpath(f"tiling_{layer_name}.pdf")
        logger.debug(f"Saving temporary tiling in '{temp_tiling_file_name}'.")
        fig.savefig(temp_tiling_file_name, bbox_inches='tight')
        plt.close("all")

    if settings.has("assembly", "sheets"):
        # For each group of materials that can be used to manufacture the tiles,
        # evaluate the cheapest combination of articles that can be purchased.
        for i, materials in enumerate(settings["assembly"]["sheets"]):
            logger.debug(f"Processing sheets assembly #{i}.")

            # Make sure that the list of sheets is not empty.
            if len(materials) == 0:
                print(f"Error in assembly list 'sheets/{i}': no materials specified.")
                return

            # Get the list of sheets that have to be purchased, and their quantity.
            components, cost, _ = wp3.named_tree_search([panel_material_data[m] for m in materials], len(visible_tiles))
            logger.debug(f"Optimal components in assembly: {components}. Total "
                         f"cost: {cost}.")

            # For each sheet type to be purchased, add a line in the bill of
            # materials that specifies how many sheets to buy (or their length in
            # the case of variable-length sheets).
            for component, quantity in components:
                logger.debug(f"Adding {quantity} units of '{component}' to the "
                             f"bill of materials.")
                url = materials_list["sheets"][component.name].get("url")
                url_md = f"[url link]({url})" if url is not None else ""
                if component.variable_size:
                    quantity = np.round(component.height, 3)
                    logger.debug(f"Changed quantity to {quantity} for "
                                 f"variable-sized component '{component}'.")
                bill_of_materials.append(wp3.BillItem(name=component.name, quantity=quantity, cost=component.unit_cost, category=f"sheets-{i}", notes=url_md))

                # Since this material has to be purchased, copy its tiling
                # scheme from the temporary folder to the project.
                tiling_file_name = tiling_temp_dir.joinpath(f"tiling_{component.name}.pdf")
                logger.info(f"Saving tiling for '{component.name}' as "
                            f"'{tiling_file_name.name}'.")
                shutil.copy(tiling_file_name, output_dir)
    else:
        logger.info("Parameter 'assembly/sheets' not found. You can add "
                    "assemblies following the instructions available at "
                    "https://github.com/francofusco/wp3#assembly-settings.")

    logger.debug(f"Removing temporary folder '{tiling_temp_dir}'.")
    shutil.rmtree(tiling_temp_dir)

    if settings.has("assembly", "leds"):
        # Process LED materials: evaluate how many LED strips have to be purchased.
        for i, materials in enumerate(settings["assembly"]["leds"]):
            logger.debug(f"Processing leds assembly #{i}.")

            # Make sure that the list of strips is not empty.
            if len(materials) == 0:
                print(f"Error in assembly list 'leds/{i}': no materials specified.")
                return

            # Check if all strips in this assembly have the same LED density.
            led_density = materials_list["leds"][materials[0]]["leds_per_meter"]
            logger.debug(f"Checking LEDs densities. {materials[0]}: "
                         f"{led_density}.")
            for m in materials[:1]:
                m_density = materials_list["leds"][m]["leds_per_meter"]
                logger.debug(f"Checking LEDs densities. {m}: {m_density}.")
                if m_density != led_density:
                    print(f"Error in assembly list 'leds/{i}'. The components "
                          f"'{materials[0]}' and '{m}' have a different amount "
                          f"of LEDs per meter.")
                    return

            # Evaluate how many LEDs should be inserted in a single strip and
            # how many meters would be needed to have all tiles filled with
            # LEDs.
            leds_per_tile_float = visible_tiles[0].perimeter() * led_density
            logger.debug(f"LEDs per tile (raw): {leds_per_tile_float}.")
            if np.allclose(np.round(leds_per_tile_float), leds_per_tile_float):
                logger.debug("The number of LEDs per tile is almost equal to "
                             "its next integer value. The difference is so "
                             "small that it likely is due to rounding errors.")
                leds_per_tile = np.round(leds_per_tile_float).astype(int)
            else:
                logger.debug("Rounding down the number of LEDs.")
                leds_per_tile = np.floor(visible_tiles[0].perimeter() * led_density).astype(int)
            required_led_length = len(visible_tiles) * leds_per_tile / led_density
            logger.debug(f"LEDs per tile: {leds_per_tile}; required strip "
                         f"length: {required_led_length}.")

            # Get the list of strips that have to be purchased, and their quantity.
            components, cost, _ = wp3.named_tree_search([wp3.Struct(name=m,
                value=materials_list["leds"][m]["number_of_leds"] / materials_list["leds"][m]["leds_per_meter"],
                cost=materials_list["leds"][m].get("cost", 0))
                for m in materials], required_led_length)
            logger.debug(f"Optimal components in assembly: {components}. Total "
                         f"cost: {cost}.")

            # For each strip type to be purchased, add a line in the bill of
            # materials that specifies how many to buy.
            for component, quantity in components:
                logger.debug(f"Adding {quantity} units of '{component}' to the "
                             f"bill of materials.")
                led_notes = f"Leds per tile: {leds_per_tile}."
                url = materials_list["leds"][component.name].get("url")
                if url is not None:
                    led_notes += f" [url link]({url})"
                bill_of_materials.append(wp3.BillItem(name=component.name, quantity=quantity, cost=component.cost, category=f"leds-{i}", notes=led_notes))

            # If wattage information is provided for all strips, try to estimate the
            # total wattage required to power the LEDs and add this information to
            # the bill of materials (as a PSU item).
            watts = sum(n*materials_list["leds"][c.name].get("watts", np.nan) for c, n in components)
            logger.debug(f"Estimated wattage of the LED assembly: {watts}.")
            if not np.isnan(watts):
                bill_of_materials.append(wp3.BillItem(name=f"{watts}W Power Supply Unit", category=f"leds-{i}", notes="The power has been estimated. You might need a lower wattage."))
            else:
                materials_with_no_watts = [c.name for c, _ in components if
                    "watts" not in materials_list["leds"][c.name]]
                logger.info(f"Could not estimate wattage for LED assembly #{i} "
                            f"since the following materials do not have the "
                            f"'watts' property: "
                            f"{', '.join(materials_with_no_watts)}.")

            # Knowing the number of LEDs per tile, we can provide a detailed scheme
            # of the wiring. This information is stored in a PDF document that can
            # be viewed by the user.
            fig, ax = wp3.tight_figure(visible_tiles)
            wp3.add_tiles_to_axes(visible_tiles, ax, copy=True, patch_color="white",
                                  border_color="lightgray")
            routing.plot_detailed_routing(best_routing, visible_tiles, leds_per_tile, ax)
            detailed_routing_file_name = output_dir.joinpath(f"wp3_routing_{leds_per_tile}_leds_per_tile.pdf")
            logger.info(f"Saving detailed routing for assembly #{i} into "
                        f"'{detailed_routing_file_name}'.")
            fig.savefig(detailed_routing_file_name, bbox_inches='tight', dpi=500)
            plt.close("all")

            # Options for SignalRGB components.
            signal_rgb_settings = settings.get("signal_rgb", wp3.SettingsDict())

            # Generate a component file for SignalRGB. The component in the
            # "Layouts" page will be a rectangle with maximum dimenions equal to
            # 100 - an arbitrary number that seems reasonable on my PC.
            width, height = wp3.get_bounding_box_size(visible_tiles)
            scale = signal_rgb_settings.get("component_size", 20) / max(width, height)
            width *= scale
            height *= scale
            signal_rgb_name_prefix = signal_rgb_settings.get("name_prefix", f"WP3 {output_dir.name}")
            signal_rgb_data = {
                "ProductName": signal_rgb_name_prefix,
                "DisplayName": signal_rgb_name_prefix,
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
                    signal_rgb_data["LedCoordinates"].append(led_coordinates.tolist())
                    signal_rgb_data["LedNames"].append(f"Led {led_idx} (tile {led_idx//leds_per_tile})")
            logger.debug(f"Created SignalRGB component "
                         f"'{signal_rgb_data['DisplayName']}' with dimenions "
                         f"{signal_rgb_data['Width']}x"
                         f"{signal_rgb_data['Height']}"
                         f"{len(signal_rgb_data['LedCoordinates'])} LEDs.")

            # Save the generated data into a JSON file that can be imported into
            # SignalRGB to define the custom LED geometry.
            signal_rgb_component_file = output_dir.joinpath(f"wp3_signal_rgb_{output_dir.name}_{leds_per_tile}_leds.json")
            logger.info(f"Saving SignalRGB component into "
                        f"'{signal_rgb_component_file}'.")
            with open(signal_rgb_component_file, "w") as f:
                json.dump(signal_rgb_data, f)

            # Generate and alternative file for SignalRGB with all LEDs in the
            # centers of the tiles.
            dev_name = f"{signal_rgb_name_prefix} centered"
            signal_rgb_data["ProductName"] = dev_name
            signal_rgb_data["DisplayName"] = dev_name
            for i, t in enumerate(best_routing[0]):
                led_coordinates = ((visible_tiles[t].center() - origin) * scale).tolist()
                led_coordinates[1] = height - led_coordinates[1]
                for j in range(leds_per_tile):
                    signal_rgb_data["LedCoordinates"][leds_per_tile*i+j] = led_coordinates
            logger.debug(f"Created SignalRGB component "
                         f"'{signal_rgb_data['DisplayName']}' with dimenions "
                         f"{signal_rgb_data['Width']}x"
                         f"{signal_rgb_data['Height']}"
                         f"{len(signal_rgb_data['LedCoordinates'])} LEDs.")

            # Save the generated data into a JSON file that can be imported into
            # SignalRGB to define the custom LED geometry.
            signal_rgb_component_file = output_dir.joinpath(f"wp3_signal_rgb_{output_dir.name}_{leds_per_tile}_leds_centered.json")
            logger.info(f"Saving SignalRGB component into "
                        f"'{signal_rgb_component_file}'.")
            with open(signal_rgb_component_file, "w") as f:
                json.dump(signal_rgb_data, f)

            # Generate a file for SignalRGB corresponding to a single tile.
            tile_width, tile_height = wp3.get_bounding_box_size([visible_tiles[0]])
            tile_scale = signal_rgb_settings.get("tile_size", 10) / max(tile_width, tile_height)
            tile_width *= tile_scale
            tile_height *= tile_scale
            tile_dev_name = f"{signal_rgb_name_prefix} tile"
            tile_signal_rgb_data = {
                "ProductName": tile_dev_name,
                "DisplayName": tile_dev_name,
                "Brand": "WP3",
                "Type": "custom",
                "LedCount": int(leds_per_tile),
                "Width": int(tile_width),
                "Height": int(tile_height),
                "LedMapping": [],
                "LedCoordinates": [],
                "LedNames": []
            }

            # Get the origin of the bounding box, to properly shift LEDs towards
            # the bottom-left corner.
            tile_origin, _ = wp3.get_bounding_box([visible_tiles[0]])

            # Store, for each LED in the tile, its name and coordinates.
            for led in visible_tiles[0].sample_perimeter(leds_per_tile, 0, border=-1):
                led_idx = len(tile_signal_rgb_data["LedMapping"])
                tile_signal_rgb_data["LedMapping"].append(led_idx)
                led_coordinates = (led-tile_origin)*tile_scale
                led_coordinates[1] = tile_height - led_coordinates[1]
                tile_signal_rgb_data["LedCoordinates"].append(led_coordinates.tolist())
                tile_signal_rgb_data["LedNames"].append(f"Led {led_idx}")
            logger.debug(f"Created SignalRGB component "
                         f"'{tile_signal_rgb_data['DisplayName']}' with "
                         f"dimenions {tile_signal_rgb_data['Width']}x"
                         f"{tile_signal_rgb_data['Height']}"
                         f"{len(tile_signal_rgb_data['LedCoordinates'])} LEDs.")

            # Save the generated data into a JSON file that can be imported into
            # SignalRGB to define the custom LED geometry.
            signal_rgb_component_file = output_dir.joinpath(f"wp3_signal_rgb_{output_dir.name}_{leds_per_tile}_leds_tile.json")
            logger.info(f"Saving SignalRGB component into "
                        f"'{signal_rgb_component_file}'.")
            with open(signal_rgb_component_file, "w") as f:
                json.dump(tile_signal_rgb_data, f)

            # Generate and alternative file for SignalRGB with all LEDs in the
            # centers of the tile.
            tile_dev_name = f"{signal_rgb_name_prefix} tile centered"
            tile_signal_rgb_data["ProductName"] = tile_dev_name
            tile_signal_rgb_data["DisplayName"] = tile_dev_name
            led_coordinates = ((visible_tiles[0].center() - tile_origin) * tile_scale).tolist()
            led_coordinates[1] = tile_height - led_coordinates[1]
            for i in range(leds_per_tile):
                tile_signal_rgb_data["LedCoordinates"][i] = led_coordinates
            logger.debug(f"Created SignalRGB component "
                         f"'{tile_signal_rgb_data['DisplayName']}' with "
                         f"dimenions {tile_signal_rgb_data['Width']}x"
                         f"{tile_signal_rgb_data['Height']}"
                         f"{len(tile_signal_rgb_data['LedCoordinates'])} LEDs.")

            # Save the generated data into a JSON file that can be imported into
            # SignalRGB to define the custom LED geometry.
            signal_rgb_component_file = output_dir.joinpath(f"wp3_signal_rgb_{output_dir.name}_{leds_per_tile}_leds_tile_centered.json")
            logger.info(f"Saving SignalRGB component into "
                        f"'{signal_rgb_component_file}'.")
            with open(signal_rgb_component_file, "w") as f:
                json.dump(tile_signal_rgb_data, f)
    else:
        logger.info("Parameter 'assembly/leds' not found. You can add "
                    "assemblies following the instructions available at "
                    "https://github.com/francofusco/wp3#assembly-settings.")

    # Add to the bill of materials one entry that corresponds to the number of
    # connectors to be purchased.
    bill_of_materials.append(wp3.BillItem(name="3 pin connectors", quantity=len(visible_tiles), category="wiring", notes="The quantity refers to male/female pairs."))

    # Print the bill of materials into a file.
    bill_of_materials_file_name = output_dir.joinpath("bill_of_materials.md")
    logger.info(f"Saving bill of materials into "
                f"'{bill_of_materials_file_name}'.")
    wp3.BillItem.dump_to_markdown(bill_of_materials,
                                  bill_of_materials_file_name)


if __name__ == "__main__":
    # Use argparse to deal with command-line arguments.
    parser = argparse.ArgumentParser(description="Create a custom design of "
                                     "A-RGB panels to be used in SignalRGB.")
    parser.add_argument("--verbose", "--info", action="store_true",
                        help="Outputs additional information on the console to "
                        "help debugging.")
    parser.add_argument("--debug", action="store_true", help="Outputs "
                        "additional information on the console to help "
                        "debugging. This is even more verbose than --verbose.")
    args = parser.parse_args()

    # Create log handler that appends all messages to a file. This allows to
    # keep a log of all runs.
    all_runs_handler = logging.FileHandler(".wp3_all_runs.log")
    all_runs_handler.setLevel(logging.DEBUG)

    # Create log handler that prints all messages to a file, but it clears its
    # content before starting. This allows to keep a long of the last run.
    last_run_handler = logging.FileHandler(".wp3_last_run.log", mode="w")
    last_run_handler.setLevel(logging.DEBUG)

    # Create a log handler that prints messages with given severity on stdout.
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.DEBUG if args.debug else logging.INFO if
                            args.verbose else logging.WARNING)

    # Setup logging.
    logging.basicConfig(format="%(levelname)s (%(name)s): %(message)s",
                        handlers=[all_runs_handler, last_run_handler,
                                  stream_handler])
    logger.setLevel(logging.DEBUG)
    logging.getLogger("wp3").setLevel(logging.DEBUG)

    # Run the main script and catch all exceptions.
    try:
        main()
    except Exception as e:
        if not isinstance(e, SystemExit):
            # Create a "fancy error message". One of the reasons for this
            # over-complicated formatting choice is that, in this way, errors
            # can be located more easily in log files.
            wraplen = 65
            msg = ["Execution stopped unexpectedly. Reason:", ""]
            msg += ["> " + s for s in textwrap.wrap(f"{type(e).__name__}: {e}", wraplen-2)]
            msg += [""]
            msg += textwrap.wrap("If this is not the result of your mistake, "
                                 "consider opening an issue at: "
                                 "https://github.com/francofusco/wp3/issues/new", wraplen)
            max_len = max(map(len, msg))
            headline = "+" + "-" * (max_len+2) + "+"
            msg_ind = ["| " + m + " " * (max_len - len(m)) + " |" for m in msg]
            logger.exception("\n".join(["\n", headline] + msg_ind +
                                       [headline, "\n"]), exc_info=e)

        # If the script is being run from the executable generated with
        # PyInstaller, it is necessary to block the execution here. Otherwise,
        # the user would not have the time to read the error message!
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            print("\nPress CTRL+C to exit, or close the terminal window.")
            try:
                while True:
                    pass
            except KeyboardInterrupt:
                pass
