import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash
from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks
    html table with all stocks owned, number of shares of each stock,
    current price of each stock, total value of each holding,
    current cash balance, total value of stocks and cash together"""

    stocks_owned = db.execute("SELECT stock_name, stock_symbol, SUM(shares) as total_shares FROM trades WHERE user_id = ? GROUP BY stock_name HAVING total_shares > 0", session["user_id"])
    cash_balance = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])[0]["cash"]

    grand_total = cash_balance
    # iterate over stocks and assign the current values to stock in stocks_owned
    for stock in stocks_owned:
        quote = lookup(stock["stock_symbol"])
        stock["name"] = quote["name"]
        stock["price"] = quote["price"]
        stock["stocks_value"] = quote["price"] * stock["total_shares"]
        grand_total += stock["stocks_value"]

    return render_template("index.html", stocks_owned = stocks_owned, cash_balance = cash_balance, grand_total = grand_total)


@app.route("/addcash", methods=["GET", "POST"])
@login_required
def addcash():

    if request.method == "GET":
        return render_template("addcash.html")

    add_cash = float(request.form.get("addcash"))

    current_cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
    current_cash = float(current_cash[0]["cash"])

    db.execute("UPDATE users SET cash = ? WHERE id = ?", current_cash + add_cash, session["user_id"])
    flash(f"{usd(add_cash)} successfully added!")

    return redirect("/")


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock, if GET then display form"""

    if request.method == "GET":
        return render_template("buy.html")

    """Require that a user input a stock's symbol, implemented as a text field whose name is symbol.
    Render an apology if the input is blank or the symbol does not exist (as per the return value of lookup)."""

    user_input_stocks = lookup(request.form.get("symbol"))
    if not user_input_stocks:
        return apology("Stocks not found", 400)

    """Require that a user input a number of shares, implemented as a text field whose name is shares.
    Render an apology if the input is not a positive integer."""
    shares_input = request.form.get("shares")

    try:
        shares_input = int(shares_input)
    except ValueError:
        return apology("Please enter a valid number", 400)

    if shares_input < 1:
        return apology("Please enter a valid number", 400)

    # SELECT how much cash the user currently has in users to see if she can afford the stocks
    user_credit = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
    user_credit = float(user_credit[0]["cash"])

    if shares_input > user_credit:
        return apology("Not enough money to buy requested stocks", 400)

    # complete transaction for purchasing stocks and update cash and user's portfolio
    db.execute("UPDATE users SET cash = ? WHERE id = ?", user_credit - (user_input_stocks['price'] * shares_input), session["user_id"])

    # insert transaction into trades table
    db.execute("INSERT INTO trades (user_id, stock_symbol, stock_name, shares, price) VALUES (?, ?, ?, ?, ?)",
               session["user_id"], user_input_stocks["symbol"], user_input_stocks["name"], shares_input, user_input_stocks["price"])


    flash(f"You bought {shares_input} shares of {user_input_stocks['name']} at ${user_input_stocks['price'] * shares_input}")

    # after successful purchase redirect to homepage
    return redirect("/")


@app.route("/changepassword", methods=["GET", "POST"])
@login_required
def changepassword():

    if request.method == "GET":
        return render_template("change.html")

    new_password = request.form.get("password")

    if not new_password or (new_password != request.form.get("confirm")):
        return apology("No password entered or password mismatch")

    db.execute("UPDATE users SET hash = ? WHERE id = ?", generate_password_hash(new_password), session["user_id"])
    flash("Password successfully updated!")

    return redirect("/")


@app.route("/history")
@login_required
def history():

    """Show history of transactions"""
    transactions = db.execute("SELECT stock_symbol, shares, price, time FROM trades WHERE user_id = ? ORDER BY time DESC", session["user_id"])

    return render_template("history.html", transactions = transactions)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():

    """if user accessed page via get (meaning no input), show html page with form where user can lookup a quote"""
    if request.method == "GET":
        return render_template("quote.html")

    # get a quote of the stock that user looked up using lookup function
    lookup_quote = lookup(request.form.get("symbol"))

    if not lookup_quote:
        return apology("Quote not found", 400)

    return render_template("quoted.html", info_quote=lookup_quote)


@app.route("/register", methods=["GET", "POST"])
def register():

    """if user accessed page via get, show register html page with form"""
    if request.method == "GET":
        return render_template("register.html")

    input_username = request.form.get("username")
    input_password = request.form.get("password")
    input_confirmation = request.form.get("confirmation")

    username_exists = db.execute("SELECT * FROM users WHERE username = ?", input_username)

    # Ensure username was submitted
    if not input_username:
        return apology("must provide username", 400)

    if username_exists:
        return apology("username already in use", 400)

    # Ensure password was submitted
    if not input_password:
        return apology("must provide password", 400)

    # Ensure confirm password was submitted
    # if not input_confirmation:
        # return apology("must confirm password", 400)

    # Ensure passwords match
    if input_confirmation != input_password:
        return apology("passwords don't match", 400)

    # if all the above checks worked out, then add new user & hash_password to database
    db.execute("INSERT INTO users (username, hash) VALUES(?, ?)", input_username, generate_password_hash(input_password))

    # log in the user that has just registered, SELECT always returns list of dicts that's why [0]["id"]
    session["user_id"] = db.execute("SELECT id FROM users WHERE username = ?", input_username)[0]["id"]
    return redirect("/")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Require that a user input a stock's symbol, implemented as a select menu whose name is symbol.
    Render an apology if the user fails to select a stock or if (somehow, once submitted) the user does not own any shares of that stock."""

    if request.method == "GET":

        stocks_owned = db.execute("SELECT stock_name, SUM(shares) as total_shares FROM trades WHERE user_id = ? GROUP BY stock_name HAVING total_shares > 0", session["user_id"])
        # if user don't own stocks
        if not stocks_owned:
            return apology("No stocks to sell")

        # show a form with user's stocks
        return render_template("sell.html", stocks_owned = stocks_owned)


    stocks_input = request.form.get("symbol")

    if not stocks_input:
        return apology("Please select stocks to sell", 400)

    shares_input = request.form.get("shares")
    try:
        shares_input = int(shares_input)
    except ValueError:
        return apology("Please enter a valid number", 400)
    if shares_input < 1:
        return apology("Please enter a valid number", 400)


    # get user's shares of selected stocks from TABLE trades
    shares_owned = db.execute("SELECT SUM(shares) as shares_owned FROM trades WHERE user_id = ? AND stock_symbol = ?", session["user_id"], stocks_input)[0]["shares_owned"]

    if not shares_owned or shares_input > shares_owned:
        return apology("You don't own enough shares", 400)

    else:
        # get current price of shares and update user's cash (money she gets for selling)
        shares_currentvalue = shares_input * lookup(stocks_input)["price"]
        flash(f"You sold {shares_input} shares of {stocks_input} at {usd(shares_currentvalue)}")

        user_credit = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
        user_credit = float(user_credit[0]["cash"])
        db.execute("UPDATE users SET cash = ? WHERE id = ?", user_credit + shares_currentvalue, session["user_id"])

        # Update the number of shares in the database
        db.execute("INSERT INTO trades (user_id, stock_symbol, stock_name, shares, price) VALUES (?, ?, ?, ?, ?)", session["user_id"], stocks_input, stocks_input, (-1* shares_input), lookup(stocks_input)["price"])

        return redirect("/")
