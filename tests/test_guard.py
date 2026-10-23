import guard


class TestCleanInput:
    def test_strips_wake_phrase(self):
        assert guard.clean_input("Hey Jack, what does PNY make?") == "what does PNY make?"

    def test_whisper_hallucinations_are_empty(self):
        for noise in ["Thank you.", " you ", "Thanks for watching!", "", "...", "Um."]:
            assert guard.clean_input(noise) == "", noise

    def test_caps_length(self):
        assert len(guard.clean_input("word " * 200)) <= guard.MAX_INPUT_CHARS

    def test_keeps_normal_question(self):
        assert guard.clean_input("  Roast   Marketing  ") == "Roast Marketing"


class TestCleanOutput:
    def test_cuts_to_three_sentences(self):
        out = guard.clean_output("This is sentence one. This is sentence two! Is this sentence three? This is sentence four.")
        assert out == "This is sentence one. This is sentence two! Is this sentence three?"

    def test_short_fragments_dont_count(self):
        line = "Rebooted. Did anyone see that happen? No? Great. I'm totally fine now."
        assert guard.clean_output(line) == line

    def test_word_cap(self):
        out = guard.clean_output(" ".join(["word"] * 100) + ".")
        assert out and len(out.split()) == guard.MAX_WORDS and out.endswith(".")

    def test_strips_markdown_emoji_and_stage_directions(self):
        out = guard.clean_output("*sighs* **Fine.** It's giving 🎃 GPU energy.")
        assert out == "Fine. It's giving GPU energy."

    def test_blocklist_returns_none(self):
        assert guard.clean_output("Well that's a shitty pumpkin.") is None

    def test_empty_returns_none(self):
        assert guard.clean_output("   ") is None
        assert guard.clean_output("*stares blankly*") is None

    def test_does_not_block_innocent_words(self):
        assert guard.clean_output("Classic Sales. Assessment pending.") is not None


class TestRepeat:
    def test_near_duplicate_detected(self):
        recent = ["Marketing A/B tested the googly eyes. Bold."]
        assert guard.is_repeat("Marketing A/B tested the googly eyes. So bold.", recent)

    def test_different_reply_passes(self):
        recent = ["Marketing A/B tested the googly eyes. Bold."]
        assert guard.is_repeat("Finance's pumpkin was approved in triplicate.", recent) is None


class TestSayFriendly:
    def test_gpu_model_numbers(self):
        assert guard.say_friendly("RTX 5090") == "R T X fifty ninety"
        assert guard.say_friendly("the RTX 5070 Ti") == "the R T X fifty seventy tie"

    def test_slash_lists_get_prefixes(self):
        out = guard.say_friendly("RTX 5080/5070 Ti/5070")
        assert out == "R T X fifty eighty, R T X fifty seventy tie, R T X fifty seventy"

    def test_ssd_model(self):
        assert guard.say_friendly("the CS3250 M.2 NVMe") == "the C S thirty two fifty M dot two N V M E"

    def test_years_untouched(self):
        assert guard.say_friendly("Founded in 1985.") == "Founded in 1985."

    def test_specs(self):
        out = guard.say_friendly("32 GB of GDDR7 at 1,792 GB/s on PCIe 5.0 x16, 2,625 MHz, 120 mm fans")
        assert out == ("32 gigabytes of G D D R 7 at 1,792 gigabytes per second on P C I E 5.0 by 16, "
                       "2,625 megahertz, 120 millimeter fans")

    def test_acronyms(self):
        assert guard.say_friendly("PNY GPUs and AI for HR") == "P N Y G P U's and A I for H R"

    def test_lowercase_it_untouched(self):
        assert guard.say_friendly("it is what it is") == "it is what it is"

    def test_two_digits(self):
        assert guard.two_digits(7) == "seven"
        assert guard.two_digits(42) == "forty two"
        assert guard.model_number("5005") == "fifty oh five"
        assert guard.model_number("4000") == "forty hundred"
