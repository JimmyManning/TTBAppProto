"""Development entrypoint for the TTB label verifier web application."""

from ttb_label_verifier import create_app

app = create_app()


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5001)
