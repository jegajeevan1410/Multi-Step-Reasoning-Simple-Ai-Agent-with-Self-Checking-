from agent import solve

TESTS = [
    ("8 + 7", "15"),
    ("45 - 18 + 6", "33"),
    ("12 * 4 / 3", "16"),
    ("10 + 20 - 33 * 2", "-36"),
    ("Alice has 3 red apples and twice as many green apples. How many apples total?", "9 apples"),
    ("Ravi has 5 pencils and three times as many pens. How many items in total?", "20 items"),
    ("Sam has 6 stickers and Mia has 4 more stickers than Sam. How many stickers in total?", "16 stickers"),
    ("I have 3 apples. If I give 1 apple to my friend, how many apples will I have left?", "2 apples"),
    ("Priya had 10 chocolates. She ate 2 and then bought 5 more. How many chocolates does she have now?", "13 chocolates"),
    ("A shop had 50 bags. It sold 18 bags in the morning and 12 bags in the evening. How many bags are left?", "20 bags"),
    ("A shopkeeper has 40 chocolates. He sells half of them in the morning. In the afternoon, he gives 5 chocolates to his friend and buys 12 more. The next day, he sells one-third of his remaining chocolates. How many chocolates does he have left?", "18 chocolates"),
    ("Anu has 80 rupees. She spends 25% on a pen and then gets 10 rupees from her mother. How many rupees does she have now?", "70 rupees"),
    ("A bus starts its journey with 40 passengers. At the first stop, 12 passengers get off and 8 get on. At the second stop, half of the passengers get off, and 6 new passengers get on. At the third stop, 5 passengers get off and 3 get on. How many passengers are on the bus now?", "22 passengers"),
    ("2, 4, 8, 16, _", "32"),
    ("3, 7, 11, 15, _", "19"),
    ("1, 4, 9, 16, _", "25"),
    ("A train leaves at 14:30 and arrives at 18:05. How long is the journey?", "3 hours 35 minutes"),
    ("A train leaves at 23:50 and arrives at 00:20. How long is the journey?", "30 minutes"),
    ("A meeting needs 60 minutes. Free slots: 09:00–09:30, 09:45–10:30, 11:00–12:00.", "11:00–12:00"),
    ("A call needs 45 minutes. Slots: 10:00–10:30, 13:15–14:00, 15:00–16:30.", "13:15–14:00 and 15:00–16:30"),
]

passed = 0
for question, expected in TESTS:
    got = solve(question)["answer"]
    ok = got == expected
    passed += ok
    print(f"[{'PASS' if ok else 'FAIL'}] {question}  ->  {got}")
print(f"\n{passed}/{len(TESTS)} correct")
