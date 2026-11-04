import re
line = "የሚሸጠው እቃ :- ሲም ካርድ (ቁጥሩ 0911975299)  "
m = re.search(r"የሚሸጠው እቃ\s*:-\s*(.*?)(?=\n|$)", line)
print("item:", repr(m.group(1)) if m else None)
