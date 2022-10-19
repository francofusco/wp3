import argparse
import pathlib
import sys


def is_comment(line):
    """Check if the given string is a comment."""
    stripped = line.lstrip()
    return len(stripped) > 0 and stripped[0] == "#"


def process(file, line_length, line_offset=1, marker="<<<<<"):
    """Finds all comment lines that are longer than a certain length.

    Args:
        file: source file to be processed.
        line_length: maximum line length, in characters, that can be present in
            a single line.
        line_offset: number to be added to the line index to report which lines
            need to be fixed.
        marker: string to be added at the end of an "offending comment line" to
            make it easier to locate it in the annotated file. If the line
            already ends with this marker, it will not be added again. However,
            a pre-existing marker is taken into account when evaluating the
            length of the line itself.
    Returns:
        processed_lines: a list of strings, which can be joined by new-line
            characters to form the annotated document.
        lines_to_fix: line numbers of "offending comment lines".
    """
    # Open the file and read its content. The variable lines will contain one
    # entry per document line, with no new-line characters at the end.
    with open(file, "r") as f:
        lines = f.read().splitlines()

    # Prepare working variables.
    processed_lines = []
    lines_to_fix = []

    for i, line in enumerate(lines):
        # Check if the given comment line is too long.
        if is_comment(line) and len(line) > line_length:
            # Keep track of line numbers that the user should fix.
            lines_to_fix.append(i + line_offset)

            # If the marker is not already there, add it to the end of the
            # offending line.
            if not line.endswith(marker):
                line = line + marker
        # Save the current line.
        processed_lines.append(line)
    # Return the result.
    return processed_lines, lines_to_fix


def main():
    # Create and parse command line arguments.
    parser = argparse.ArgumentParser(
        description=(
            "Check one or more files and reports where inside it comments are"
            " too long."
        )
    )
    parser.add_argument(
        "targets",
        nargs="+",
        help=(
            "Files or directories to be checked. Files found inside directories"
            " are accepted only if they have '.py' extension."
        ),
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="If given, directories are explored recursively.",
    )
    parser.add_argument(
        "--exclude",
        nargs="+",
        default=[],
        help="List of files or directories to be excluded.",
    )
    parser.add_argument(
        "--line_length",
        type=int,
        default=80,
        help="Maximum line length (needed to report long comments).",
    )
    parser.add_argument(
        "--annotate",
        action="store_true",
        help="If given, add an annotation at the end of long lines.",
    )

    args = parser.parse_args()

    # Exit code to report errors. Initially set to zero and changed to 1 as soon
    # as something goes wrong.
    exit_code = 0

    # List of input paths, divided into existing files and directories.
    paths = [pathlib.Path(t) for t in args.targets]
    excluded = [pathlib.Path(e) for e in args.exclude]
    files = [p for p in paths if p.is_file() and p not in excluded]

    # For each directory, extract its files (recursively, if needed).
    directories = [p for p in paths if p.is_dir() and p not in excluded]
    for dir in directories:
        new_targets = dir.glob("**/*.py" if args.recursive else "*.py")
        files += [t for t in new_targets if t not in excluded]

    # Report all invalid paths.
    invalid = [p for p in paths if not p.exists()]
    for path in invalid:
        exit_code = 1
        print("Invalid (non existent) path", path)

    for file in files:
        # Process the current file adn find offending lines.
        out, bad_lines = process(file, args.line_length)
        if len(bad_lines) > 0:
            # If at least one offending comment is found, set the exit code to
            # '1' (failure) and report the issue.
            exit_code = 1
            print(f"File {file} has {len(bad_lines)} lines to fix.")
            print("Lines:", ", ".join(map(str, bad_lines)))
            print()

            # If requested, overwrite the file by adding the desired markers.
            if args.annotate:
                with open(file, "w") as f:
                    f.write("\n".join(out))

    # Exit with the correct code.
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
