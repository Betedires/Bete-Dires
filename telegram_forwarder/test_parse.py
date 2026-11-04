import re

def strip_emojis_from_line(line):
    return re.sub(r'^[\U00010000-\U0010ffff\u2600-\u26FF\u2700-\u27BF\U0001F300-\U0001FAFF\u00A9\u00AE\u203C\u2049\u20E3\u2122\u2139\u231A\u231B\u23E9-\u23F3\u23F8-\u23FA\u24C2\u25AA\u25AB\u25B6\u25C0\u25FB-\u25FE\u2600-\u2604\u260E\u2611\u2614\u2615\u2618\u261D\u2620\u2622\u2623\u2626\u262A\u262E\u262F\u2638-\u263A\u2640\u2642\u2648-\u2653\u265F\u2660\u2663\u2665\u2666\u2668\u267B\u267E\u267F\u2692-\u2697\u2699\u269B\u269C\u26A0\u26A1\u26AA\u26AB\u26B0\u26B1\u26BD\u26BE\u26C4\u26C5\u26CE\u26CF\u26D1\u26D3\u26D4\u26E9\u26EA\u26F0-\u26F5\u26F7-\u26FA\u26FD\u2702\u2705\u2708-\u270D\u270F\u2712\u2714\u2716\u271D\u2721\u2728\u2733\u2734\u2744\u2747\u274C\u274E\u2753-\u2755\u2757\u2763\u2764\u2795-\u2797\u27A1\u27B0\u27BF\u2934\u2935\u2B05-\u2B07\u2B1B\u2B1C\u2B50\u2B55\u3030\u303D\u3297\u3299🟡🟢🔴🔵🟠🟣⚫⚪🟤]+\s*', '', line)

text = """የሚሸጠው እቃ :- ሲም ካርድ (ቁጥሩ 0911975299)

🟡 ዋጋ እና አድራሻ :- 7 ሺ ብር (አየር ጤና)

🟡የባለቤቱ ቁጥር :- +251911848337

🟡የባለቤቱ Inbox :- -

🟡የእቃው መለያ ቁጥር :- 2268"""

cleaned_lines = [strip_emojis_from_line(line) for line in text.splitlines()]
cleaned_text = '\n'.join(cleaned_lines)

price_loc_match = re.search(r'ዋጋ[^\n:]*:-\s*([^\(\n]+?)(?:\s*\(([^\)\n]+)\))?\s*$', cleaned_text, re.MULTILINE)
if price_loc_match:
    print('Match:', price_loc_match.groups())
else:
    print('No match for price/loc')
