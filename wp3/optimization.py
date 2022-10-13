from .tile import Tile, unique_vertices
import logging
import numpy as np

logger = logging.getLogger(__name__)


class Routing:
    """Class that allows to model the routing problem.

    It contains two fields: `vertices` and `tiles`. The former is a
    NumPy array with shape `(n_vertices, 2)`, such that `vertices[i]` gives
    the Cartesian coordinates of the i-th unique vertex, across all tiles.
    The latter is a list with N-dimensional integer-valued arrays, corresponding
    to the indices of the N vertices that belong to that tile. In practice,
    `vertices[tiles[j,k]]` provides the Cartesian coordinates of the the k-th
    vertex of the j-th tile.
    """

    def __init__(self, tiles, segments=1):
        """Create data to be used to find an optimal cable routing.

        Args:
            tiles: a list of Tile instances. They should correspond to tiles
                of the same type, in terms of both subclass and geometric
                parameters.
            segments: how many segments should be used for routing. With 1
                segment, the solution is a single path from start to finish.
                Otherwise, the solution uses multiple segments with
                interruptions in between. The ending tile of each segment can
                be found in the variable cuts.
        """
        # It does not make sense to perform routing for less than two tiles.
        if len(tiles) < 2:
            raise ValueError(
                "The number of tiles in a routing problem should "
                f"be at least two, not {len(tiles)}."
            )

        # The most segments we can produce is one per tile.
        if not (1 <= segments <= len(tiles)):
            raise ValueError(
                "Invalid number of segments given to the routing "
                "algorithm. The number of segments must be "
                f"between 1 and {len(tiles)} (number of tiles). "
                f"Received value: {segments}."
            )

        # List of all unique 2D points in the group of tile vertices.
        self.vertices = unique_vertices(tiles)

        # Create a list that provides, for each tile, the included vertices.
        tiles_indices = []

        for tile in tiles:
            # This is a fast (maybe convoluted) way to create a matrix of
            # squared distances, such that vector_distances[i,j] provides the
            # displacement between the vertex vertices[i] and the j-th vertex of
            # the tile.
            vector_distances = self.vertices.reshape(-1, 1, 2) - tile.vertices(
                border=0.5
            ).reshape(1, -1, 2)

            # Using Einstein's summation, convert displacement vectors into scalars.
            # The result is a matrix D whose elements D[i,j] are the squared
            # distances between vertices[i] and the j-th vertex of the tile. By
            # taking argmin along the first axis, we are left with six values:
            # they represent the indices of each vertex of the tile.
            tiles_indices.append(
                np.einsum(
                    "ijk,ijk->ij", vector_distances, vector_distances
                ).argmin(axis=0)
            )

        # Convert into an array.
        self.tiles = np.array(tiles_indices)

        # Store some dimensions for faster and clearer access.
        self.n_vertices = len(self.vertices)
        self.n_tiles, self.vertices_per_tile = self.tiles.shape

        # Allow cutting into multiple segments.
        if segments > 1:
            self.cuts = [
                c[-1]
                for c in np.array_split(np.arange(self.n_tiles), segments)[:-1]
            ]
        else:
            self.cuts = []

        logger.debug(
            f"Create routing problem with {self.n_tiles} and "
            f"{self.n_vertices} unique vertices. The routing consists "
            f"of {segments} segments, with cuts made at the samples "
            f"{self.cuts}. The list that gives for each tile which "
            f"vertices it contains is:\n{self.tiles}"
        )

    def random_sample(self):
        """Create a routing sample at random.

        Returns:
            A list containing tuples (i,j), representing a routing candidate.
            The list (i1,j1), (i2,j2), ... means that we start by visiting the
            tile i1, passing through its vertex j1. The choices are completely
            randomized. The actual ouput is a NumPy array with shape
            (2, n_tiles) for ease of use in the rest of the code.
        """
        return np.stack(
            (
                np.random.permutation(self.n_tiles),
                np.random.choice(self.vertices_per_tile, size=self.n_tiles),
            )
        )

    def evaluate_cost(self, sample, repetition_penalty=100):
        """Calculate the cost of the given sample.

        Args:
            sample: a NumPy array with shape (2, n_tiles). The meaning of its
                entries is explained in the method random_sample().
            repetition_penalty: no vertex in the group of tiles should be
                visited more than once. This is a hard constraint, in theory,
                but it can be modelled as a soft one by heaviliy penalize its
                violation by adding to the total cost the number of repetitions
                multiplied by this coefficient.
        Returns:
            A scalar cost in the range [0, inf). The cost is the sum of the
            total path length plus the penalty for visiting the same vertex
            multiple times.
        """
        # Get the sequence of vertex indices from the sample.
        index_sequence = self.tiles[sample[0], sample[1]]

        # Calculate the length of the routing path.
        d = np.diff(self.vertices[index_sequence], axis=0)
        d[self.cuts] = 0
        path_length = np.sum(np.sqrt(np.einsum("ij,ij->i", d, d)))

        # Count how many times vertices are repeated. Ideally, we would like
        # each vertex to be visited at most once. We thus have to penalize any
        # further appearances. As an example, if the list is
        #   [1, 2, 1, 3, 4, 4, 4]
        # then both 1 and 4 appear more than once. The code would evaluate that
        # the number 1 has one repetition, while number 4 has two, for a total
        # of 3 repetitions.
        appearances = np.zeros(self.n_vertices)
        for i in index_sequence:
            appearances[i] += 1
        repetitions = np.sum(appearances[appearances > 1])

        # Return the cost as the sum of the total length plus a heavy penalty
        # on the number of repetitions.
        return path_length + repetition_penalty * repetitions

    def mutate_vertex(self, sample, tile_index, increment):
        """Change which vertex of a tile is used.

        The method modifies the sample so that another vertex is used for a
        selected tile.

        Note that the sample is mutated in-place, with the return value being
        just a reference to the original input. If you want to create a mutation
        from an existing sequence without modifying it, you could consider using
        the syntax `new_sample = routing.mutate_vertex(sample.copy(), ...)`.

        Args:
            sample: a NumPy array with shape (2, n_tiles), to be mutated
                in-place. The meaning of its entries is explained in the method
                random_sample().
            tile_index: index (inside the sample) of the tile to be considered
                in the mutation.
            increment: indices are mutated in a circular fashion. This parameter
                tells how many steps to perform. As an example, increment=1
                means to select the next vertex in the tile, increment=2 to
                select the second next, etc. If increment is equal to the number
                of vertices in a single tile, the sample does not change.
        Returns:
            A reference to the mutated sample. Note that the sample is mutated
            in-place: the return value is available just for convenience.
        """
        sample[1, tile_index] = (
            sample[1, tile_index] + increment
        ) % self.vertices_per_tile
        return sample

    def mutate_order(self, sample, tile_index, distance):
        """Swap the order in which two tiles are visited.

        The method modifies the sample so that the first selected tile is
        visited when the second one was supposed to be visited, and viceversa.
        As an example, consider a sample with 5 tiles labelled from T1 to T5, to
        be visited in the order [T3, T5, T1, T2, T4]. If the parameters are so
        that we select the second and fifth tiles in the sequence, after the
        mutation the sample would be [T3, T4, T1, T2, T5].

        Note that the sample is mutated in-place, with the return value being
        just a reference to the original input. If you want to create a mutation
        from an existing sequence without modifying it, you could consider using
        the syntax `new_sample = routing.mutate_order(sample.copy(), ...)`.

        Args:
            sample: a NumPy array with shape (2, n_tiles), to be mutated
                in-place. The meaning of its entries is explained in the method
                random_sample().
            tile_index: index (inside the sample) of the first tile to be
                considered in the mutation.
            distance: value added to tile_index to determine the second tile to
                be considered in the mutation. As an example, with distance set
                to 1, the tile that immediately follows that in position
                tile_index is selected. If there are not enough tiles after the
                first one, the index "overflows", letting one to select tiles
                that come before the first selection. As an example, if there
                are 10 tiles and the parameters are tile_index=8 and distance=4,
                the second tile would be that in position (8+4)%10=2, ie, the
                third tile.
        Returns:
            A reference to the mutated sample. Note that the sample is mutated
            in-place: the return value is available just for convenience.
        """
        next_tile_index = (tile_index + distance) % self.n_tiles
        sample[:, [tile_index, next_tile_index]] = sample[
            :, [next_tile_index, tile_index]
        ]
        return sample

    def mutate_vertex_then_order(
        self, sample, tile_index, vertex_increment, tile_distance
    ):
        """Combine mutate_vertex and mutate_order in a single call.

        This method selects one tile and changes the vertex that should be
        visited in it. Then, it selects another tile and swaps their visting
        orders. The result is literally obtained by calling mutate_vertex() and
        mutate_order() in cascade.

        Args:
            sample: a NumPy array with shape (2, n_tiles), to be mutated
                in-place. The meaning of its entries is explained in the method
                random_sample().
            tile_index: see mutate_vertex() and mutate_order().
            vertex_increment: see the parameter increment in mutate_vertex().
            tile_distance: see the parameter distance in mutate_order().
        Returns:
            A reference to the mutated sample. Note that the sample is mutated
            in-place: the return value is available just for convenience.
        """
        self.mutate_vertex(sample, tile_index, vertex_increment)
        self.mutate_order(sample, tile_index, tile_distance)
        return sample

    def improve(self, sample, cost, attempts, max_distance, mixed_mutations):
        """Try to improve the given sample using few random moves.

        This method takes a sample as input and tries to improve it by
        performing a certain amount of pseudo-random moves. More precisely, it
        selects one tile at random and generates a set of mutations by:
        - Changing its used vertex to all possible alternatives
        - Swapping its order with all its successors within a certain range
        - Doing a mix of the two (for a limited amount of random candidates)
        It then computes the cost of these mutations and selects the best one.
        If this is an improvement with respect to the previous sample, it
        accepts it as new sample and repeats the process once again. If there is
        no improvement, it takes note that one more attempt at improving the
        sample failed and retries. The method returns once the number of failed
        attempts reaches a given maximum.

        Args:
            sample: a NumPy array with shape (2, n_tiles), to be improved via
                mutation. The meaning of its entries is explained in the method
                random_sample().
            cost: cost of the provided sample (see evaluate_cost()).
            attempts: maximum number of improvement attempts that can be failed
                before exiting the method.
            max_distance: maximum value that can be passed as 'distance' to the
                methods mutate_order() and mutate_vertex_then_order().
            mixed_mutations: number of mutations that involve both a change in
                vertex and order to be generated.
        Returns:
            mutation: if possible, a new mutation that is an improvement of the
                original sample. If this is not possible, a reference to the
                original sample is returned.
            cost: the cost of the returned mutation, or the original cost if no
                improvement was possible.
        """
        # Select a random tile.
        t = np.random.randint(self.n_tiles)

        # Generate several mutations.
        mutations = (
            [
                self.mutate_vertex(sample.copy(), t, i)
                for i in range(1, self.vertices_per_tile)
            ]
            + [
                self.mutate_order(sample.copy(), t, i)
                for i in range(1, max_distance)
            ]
            + [
                self.mutate_vertex_then_order(
                    sample.copy(),
                    t,
                    np.random.randint(1, self.vertices_per_tile),
                    np.random.randint(1, max_distance),
                )
                for _ in range(mixed_mutations)
            ]
        )

        # Evaluate the cost of each mutation and look for the best one.
        costs = [self.evaluate_cost(mutation) for mutation in mutations]
        idx = np.argmin(costs)

        # Check if the best mutation provides an improvement, and decide what to
        # do next.
        if costs[idx] < cost:
            # If the mutation is an improvement, keep it and keep trying to get
            # better solutions.
            return self.improve(
                mutations[idx],
                costs[idx],
                attempts,
                max_distance,
                mixed_mutations,
            )
        elif attempts > 0:
            # If the mutation is not an improvement, reject it. Reduce the
            # number of possible attempts by one and restart all over.
            return self.improve(
                sample, cost, attempts - 1, max_distance, mixed_mutations
            )
        else:
            # If the mutation is not an improvement and there are no further
            # attempts remaining, return the current sample and its cost.
            return sample, cost

    def optimize(
        self,
        best_sample=None,
        max_iterations=100,
        attemps_per_improvement=100,
        random_start_probability=0.9,
        max_swap_distance=10,
        mixed_mutations=10,
        progressbar_length=30,
        progressbar_char="#",
        percentage_precision=0,
    ):
        """Look for an optimal routing.

        The algorithm is a quite simple iterative procedure. At each iteration,
        it does the following:

        1. Select an initial sample, either at random or by copying the current
           best guess.
        2. Try to reach a better solution using the improve() method, which
           performs pseudo-random mutations on the sample.
        3. If the current best guess has a higher cost than the output of the
           improve() method, replace it with the new solution.

        The algorithm stops after a certain number of iterations have been
        performed, or by a user interruption (via SIGINT/CTRL+C).

        Args:
            best_sample: an initial guess, possibly representing a previously
                obtained solution. If not given, a random one is generated.
            max_iterations: number of times the main loop (that generates new
                samples and tries to improve them) is executed.
            attemps_per_improvement: number of attempts passed to each call to
                improve().
            random_start_probability: probability of picking a random start at
                each main iteration - as opposed to using the current best
                guess.
            max_swap_distance: passed to each call to improve() as the value for
                the parameter max_distance.
            mixed_mutations: passed to each call to improve() as the value for
                the parameter mixed_mutations.
            progressbar_length: length (in number of characters) of the progress
                bar that is shown during the optimization.
            progressbar_char: character used to fill the progress bar.
            percentage_precision: number of decimal digits to show in the
                percentage that is displayed next to the progress bar.
        """
        # If no warm-start was given, start from a random sample.
        if best_sample is None:
            logger.debug("Creating initial candidate at random.")
            best_sample = self.random_sample()

        # Get the cost of the available routing.
        best_cost = self.evaluate_cost(best_sample)
        logger.debug(
            f"Initial candidate cost: {best_cost}."
            f" Candidate:\n{best_sample.tolist()}"
        )

        # Make sure that the swap distance makes sense.
        max_swap_distance = max(1, min(self.n_tiles - 1, max_swap_distance))
        logger.debug(f"Using {max_swap_distance=}.")

        # Try to refine the solution. Allow the user to interrupt the search via
        # keyboard interrupts, aka, SIGINT or CTRL+C.
        print("Routing in progress (CTRL+C to interrupt).")
        try:
            logger.debug("Routing started.")
            for iter in range(max_iterations):
                # Show progress information, so that the user can estimate the
                # time to completion.
                progress = np.round(
                    progressbar_length * (iter + 1) / max_iterations
                ).astype(int)
                progress_percentage = np.round(
                    100 * (iter + 1) / max_iterations, percentage_precision
                )
                if percentage_precision > 0:
                    progress_percentage = np.format_float_positional(
                        progress_percentage,
                        unique=False,
                        precision=percentage_precision,
                    )
                else:
                    progress_percentage = progress_percentage.astype(int)
                print(
                    f"\r[{progressbar_char*progress}{' '*(progressbar_length-progress)}]"
                    f" {progress_percentage}%",
                    end="",
                    flush=True,
                )

                # Select a sample and try to improve it. The samples will
                # usually be a random guess, but it could sometimes be the
                # current optimal solution.
                pick_best = random_start_probability < np.random.uniform()
                sample = (
                    best_sample.copy() if pick_best else self.random_sample()
                )
                sample, cost = self.improve(
                    sample,
                    self.evaluate_cost(sample),
                    attemps_per_improvement,
                    max_swap_distance,
                    mixed_mutations,
                )
                logger.debug(
                    f"Routing iteration {iter}. Started from "
                    f"{'best' if pick_best else 'random'} sample. "
                    f"Generated new sample with cost {cost}."
                )

                # Keep track of the running best.
                if cost < best_cost:
                    best_sample = sample.copy()
                    best_cost = cost
                    logger.debug(
                        f"Found better candidate! Cost: {best_cost}. "
                        f"Candidate:\n{best_sample.tolist()}"
                    )
        except KeyboardInterrupt:
            logger.debug("Routing interrupted by user.")
        # Print a new line since print calls in the loop remain on the same one.
        print()
        logger.debug(
            f"Routing completed. Best cost: {best_cost}. "
            f"Candidate:\n{best_sample.tolist()}"
        )

        # Return the best routing found so far.
        return best_sample

    def get_detailed_routing_points(self, sample, tiles, vertices_per_tile):
        segments = []
        current_segment = np.empty((0, 2))

        for i in range(self.n_tiles):
            points = tiles[sample[0, i]].sample_perimeter(
                vertices_per_tile, sample[1, i], border=-1
            )
            current_segment = np.vstack((current_segment, points))
            if i in self.cuts:
                segments.append(current_segment)
                current_segment = np.empty((0, 2))

        segments.append(current_segment)
        return segments

    def plot_routing(self, sample, tiles, ax, alpha=0.2):
        """Plot a routing sequence in a figure."""
        vertex_sequence = self.vertices[self.tiles[sample[0], sample[1]]]

        for i in range(self.n_tiles):
            tile = tiles[sample[0, i]]
            p = (1 - alpha) * vertex_sequence[i] + alpha * np.array(
                [tile.x, tile.y]
            )
            ax.plot(*p, "o", color="black")
            if i > 0 and i - 1 not in self.cuts:
                d = p - prev_p
                ax.arrow(
                    *prev_p,
                    *d,
                    color="black",
                    linewidth=0.5,
                    head_width=0.01,
                    length_includes_head=True,
                )
            prev_p = p

        for i, tile in enumerate(tiles):
            ax.text(
                tile.x,
                tile.y,
                str(i),
                color="red",
                horizontalalignment="center",
            )

    def plot_detailed_routing(self, sample, tiles, vertices_per_tile, ax):
        """Plot a routing sequence in a figure."""
        segments = self.get_detailed_routing_points(
            sample, tiles, vertices_per_tile
        )
        all_routing_points = np.vstack(segments)

        for segment in segments:
            ax.plot(
                segment[:, 0],
                segment[:, 1],
                linewidth=1,
                marker="o",
                markevery=[0],
            )

        for i, p in enumerate(all_routing_points):
            ax.text(
                *p,
                str(i),
                color="black",
                horizontalalignment="center",
                verticalalignment="center",
                fontsize=4,
                fontweight="bold",
            )

        for i, tile in enumerate(tiles):
            ax.text(
                tile.x,
                tile.y,
                str(i),
                color="black",
                horizontalalignment="center",
                verticalalignment="center",
            )


def tree_search(
    choices, target, sequence=None, current_value=0, current_cost=0
):
    """Optimization algorithm to evaluate best combination of elements.

    Problem statement: a set of items are available, each with an associated
    value and cost. One can choose any combination of the available items (with
    repetitions) with the only constraint that removing any of the elements will
    make the total value drop below a given target. The goal is to find the
    valid combination whose total cost is minimal. If multiple solutions exist,
    then the one that also maximizes the difference between the total value and
    the target is prioritized. If this still leads to multiple solutions, the
    one that has the list amount of elements is selected.

    The algorithm is quite generic. It can be used, as an example, to evaluate
    how many LED strips to purchase. In this case, one could use the length of
    the strip as value and its cost as, well, cost. The target would be the
    total length needed. As an example, if one could choose between a 1m strip
    sold at 10$ and a 5m one worth 15$, and needs a total of 11m of strips, the
    algorithm would find that the best solution would be to buy two strips that
    are 5m long and one that is 1m long, for a total of 40$. If 13m were needed,
    the algorithm would instead suggest to buy 3 strips of 5m each, for a total
    of 15m and a cost of 45$. This is better than any other combination, such as
    buying 2 5m strips and 3 1m strips, which would result in 13m of length at
    a cost of 60$.

    Args:
        choices: a list of objects, each of which must have the fields "value"
            and "cost".
        target: the total value that a sequence must reach to be valid.
        sequence: if given, it represents a partial solution of already selected
            items. The parameter is mainly intended for internal use.
        current_value: if given, it represents the value of the partial
            solution. The parameter is mainly intended for internal use.
        current_cost: if given, it represents the cost of the partial solution.
            The parameter is mainly intended for internal use.
    Returns:
        best_sequence: sequence of items to select. It is sorted with the same
            orded of items in `choices`. Items can appear multiple times.
        best_cost: cost of the sequence.
        best_value: total value of the sequence.
    """
    # Prepare working variables.
    if sequence is None:
        sequence = []
    best_sequence = []
    best_cost = np.inf
    best_value = -np.inf

    # Print debug output using a smart indentation to allow easier debugging.
    msg_indent = "  " * len(sequence)
    logger.debug(
        f"{msg_indent}Depth: {len(sequence)}. Value: "
        f"{current_value}/{target}. Current cost: {current_cost}."
    )

    for i, elem in enumerate(choices):
        logger.debug(f"{msg_indent}Exploring choice {i}.")

        # Add value and cost
        new_value = current_value + elem.value
        new_cost = current_cost + elem.cost
        new_sequence = sequence + [elem]

        if new_cost > best_cost:
            logger.debug(
                f"{msg_indent}Early pruning of choice {i} due to "
                f"excessive partial cost {new_cost}."
            )
            continue

        # If we did not reach a terminal state, get it using recursion.
        if new_value < target:
            new_sequence, new_cost, new_value = tree_search(
                choices[i:],
                target,
                sequence=new_sequence,
                current_value=new_value,
                current_cost=new_cost,
            )
        logger.debug(
            f"{msg_indent}Choice {i}: value={new_value}/{target},"
            f" cost={new_cost}."
        )

        # Check the current solution. If it is the best found so far, store it.
        if new_cost < best_cost or (
            new_cost == best_cost
            and (
                new_value > best_value
                or (
                    new_value == best_value
                    and len(new_sequence) < len(best_sequence)
                )
            )
        ):
            best_cost = new_cost
            best_value = new_value
            best_sequence = new_sequence
            logger.debug(f"{msg_indent}Choice {i} is now the best candidate.")

    logger.debug(
        f"{msg_indent}Search completed. Value: {best_value}/{target}. "
        f"Cost: {best_cost}."
    )

    # Return the optimal result, with its cost and value as well.
    return best_sequence, best_cost, best_value


def named_tree_search(named_choices, target):
    """Optimization algorithm to evaluate best combination of elements.

    This is a variant of `tree_search`. It assumes that the choices have an
    additional "name" field, that can be used to distinguish between choices.
    Using this field, the original solution is modified to be a list of pairs
    (item, amount), telling how many units of each item are to be used.

    Args:
        choices: a list of objects, each of which must have the fields "value",
            "cost" and "name". Note that if multiple items share the same name,
            the solution might be wrong, especially if these items have
            different values and/or costs.
        target: the total value that a combination must reach to be valid.
    Returns:
        best_sequence: sequence of tuples (item, amount), representing the items
            to select and their quantity.
        best_cost: cost of the sequence.
        best_value: total value of the sequence.
    """
    logger.debug("Performing optimization using 'tree_search'.")

    # Solve the problem using the vanilla tree_search.
    best_sequence, best_cost, best_value = tree_search(named_choices, target)

    # Handle empty solutions (even though they should not be possible).
    if len(best_sequence) == 0:
        return []

    # Prepare a list of unique items and their frequency.
    unique_elements = [best_sequence[0]]
    frequency = [1]
    logger.debug(
        f"Initializing frequency of element '{unique_elements[0].name}' to 1."
    )

    # Scan all items in the solution (except the first one, which has been
    # processed already).
    for elem in best_sequence[1:]:
        # If the current element has been found already, increment its
        # frequency. Otherwise, add it and set its frequency to one.
        if elem.name == unique_elements[-1].name:
            frequency[-1] += 1
            logger.debug(
                f"Increasing frequency of '{elem.name}' to '{frequency[-1]}'."
            )
        else:
            unique_elements.append(elem)
            frequency.append(1)
            logger.debug(f"Added new element '{elem.name}'.")

    # Return the solution as a list of (item, amount) tuples.
    return (
        [(elem, freq) for elem, freq in zip(unique_elements, frequency)],
        best_cost,
        best_value,
    )
