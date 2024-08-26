def sell():
    # get user's stocks
    stocks = db.execute("SELECT stock_symbol, SUM(shares) as total_shares FROM trades WHERE user_id =? GROUP BY symbol HAVING total_shares > 0", session["user_id"])

    # if user submits form
    if request.method == "POST":
        symbol = request.form.get("symbol").upper()
        name = request.form.get("name").upper()
        shares = request.form.get("shares")

        if not symbol:
            return apology("must provide symbol")
        if not shares or not shares.isdigit() or int(shares) <= 0:
            return apology("must provide a positive integer number of shares")

        shares = int(shares)

        for stock in stocks:
            if stock["symbol"] == symbol:
                if stock["total_shares"] < shares:
                    return apology("not enough shares")

                # get quote
                quote = lookup(symbol)
                if quote is None:
                    return apology("symbol not found")
                price = quote["price"]
                total_sale = shares * price

                # update users table
                db.execute("UPDATE users SET cash = cash + :total_sale WHERE id =?", total_sale=total_sale, session["user_id"])

                # add sale to history table
                db.execute("INSERT INTO trades (user_id, stock_symbol, stock_name, shares, price) VALUES(?, ?, ?, ?, ?)", session["user_id"], symbol, name, shares, price)

                flash(f"Sold {shares} shares of {symbol} for {usd(total_sale)}")
                return redirect("/")

        return apology("symbol not found")

    return render_template("sell.html", stocks_owned= stocks)
