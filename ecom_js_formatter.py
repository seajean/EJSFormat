import sublime, sublime_plugin, re, sys, os

directory = os.path.dirname(os.path.realpath(__file__))
libs_path = os.path.join(directory, "libs")

# crazyness to get jsbeautifier.unpackers to actually import
# with sublime's weird hackery of the path and module loading
if libs_path not in sys.path:
	sys.path.append(libs_path)

# if you don't explicitly import jsbeautifier.unpackers here things will bomb out,
# even though we don't use it directly.....
import jsbeautifier, jsbeautifier.unpackers
import merge_utils

s = None

def plugin_loaded():
	global s
	s = sublime.load_settings("EcomJsFormat.sublime-settings")

if sys.version_info < (3, 0):
	plugin_loaded()

class PreSaveFormatListner(sublime_plugin.EventListener):
	"""Event listener to run JsFormat during the presave event"""
	def on_pre_save(self, view):
		fName = view.file_name()
		vSettings = view.settings()
		syntaxPath = vSettings.get('syntax')
		syntax = ""
		ext = ""

		if (fName != None): # file exists, pull syntax type from extension
			ext = os.path.splitext(fName)[1][1:]
		if(syntaxPath != None):
			syntax = os.path.splitext(syntaxPath)[0].split('/')[-1].lower()

		formatFile = ext in ['js', 'json'] or "javascript" in syntax or "json" in syntax

		if(s.get("format_on_save") == True and formatFile):
			view.run_command("js_format")


class EcomJsFormatCommand(sublime_plugin.TextCommand):
	def run(self, edit):
		settings = self.view.settings()

		# settings
		opts = jsbeautifier.default_options()
		opts.indent_char = " " #if settings.get("translate_tabs_to_spaces") else "\t"  simply ignore setting 
		opts.indent_size = int(settings.get("tab_size")) if opts.indent_char == " " else 1
		opts.max_preserve_newlines = s.get("max_preserve_newlines") or 3
		opts.preserve_newlines = s.get("preserve_newlines") or True
		opts.jslint_happy = s.get("jslint_happy") or False
		opts.brace_style = s.get("brace_style") or "collapse"
		opts.keep_array_indentation = s.get("keep_array_indentation") or False
		opts.keep_function_indentation = s.get("keep_function_indentation") or False
		opts.indent_with_tabs = s.get("indent_with_tabs") or False
		opts.eval_code = s.get("eval_code") or False
		opts.unescape_strings = s.get("unescape_strings") or False
		opts.break_chained_methods = s.get("break_chained_methods") or False

		selection = self.view.sel()[0]
		nwsOffset = self.prev_non_whitespace()

		# do formatting and replacement
		replaceRegion = None
		formatSelection = False

		# formatting a selection/highlighted area
		if(len(selection) > 0):
			formatSelection = True
			replaceRegion = selection

		# formatting the entire file
		else:
			replaceRegion = sublime.Region(0, self.view.size())

		orig = self.view.substr(replaceRegion)
		res = jsbeautifier.beautify(orig, opts)

		_, err = merge_utils.merge_code(self.view, edit, orig, res)
		if err:
			sublime.error_message("EcomJsFormat: Merge failure: '%s'" % err)

		# re-place cursor
		offset = self.get_nws_offset(nwsOffset, self.view.substr(sublime.Region(0, self.view.size())))
		rc = self.view.rowcol(offset)
		pt = self.view.text_point(rc[0], rc[1])
		sel = self.view.sel()
		sel.clear()
		self.view.sel().add(sublime.Region(pt))

		self.view.show_at_center(pt)


	def prev_non_whitespace(self):
		pos = self.view.sel()[0].a
		preTxt = self.view.substr(sublime.Region(0, pos));
		return len(re.findall('\S', preTxt))

	def get_nws_offset(self, nonWsChars, buff):
		nonWsSeen = 0
		offset = 0
		for i in range(0, len(buff)):
			offset += 1
			if not(buff[i].isspace()):
				nonWsSeen += 1

			if(nonWsSeen == nonWsChars):
				break

		return offset


class EcomCssFormat(sublime_plugin.TextCommand):
    def run(self, edit, action='compact'):
        rule_starts = self.view.find_all('\{')
        rule_ends = self.view.find_all('\}')
 
        rules_regions = list()
        regions_to_process = list()
 
        selections = self.view.sel()
        if len(selections) == 1 and selections[0].empty():
            selections = [sublime.Region(0, self.view.size())]
 
        for i in range(len(rule_starts)):
            rule_region = sublime.Region(rule_starts[i].a, rule_ends[i].b)
            rules_regions.append(rule_region)
            for sel in selections:
                if sel.intersects(rule_region):
                    regions_to_process.append(rule_region)
                    break
 
        regions_to_process.reverse()
        self.process_rules_regions(regions_to_process, action, edit)
 
    def process_rules_regions(self, regions, action, edit):
        actions = {
            'compact': self.compact_rules,
            'expand': self.expand_rules,
            'toggle': self.toggle_rules
        }
        actions[action](regions, edit)
 
    def toggle_rules(self, regions, edit):
        grouped_rules = list()
 
        for r in regions:
            action_key = 'expand' if self.rule_is_compact(r) else 'compact'
 
            if not grouped_rules or not action_key in grouped_rules[-1]:
                grouped_rules.append({action_key: []})
 
            grouped_rules[-1][action_key].append(r)
 
        for group in grouped_rules:
            for (action, rules) in group.items():
                self.process_rules_regions(rules, action, edit)
 
    def compact_rules(self, regions, edit):
        view = self.view
 
        for collapse_region in regions:
            content = view.substr(collapse_region)
 
            match = re.match(r"\{([^\}]*)\}", content)
 
            rules = match.group(1).split(';')
            rules = [r.strip() for r in rules]
            rules = '; '.join(rules)
 
            view.replace(edit, collapse_region, '{ ' + rules + '}')
 
    def expand_rules(self, regions, edit):
        view = self.view
 
        for expand_region in regions:
            content = view.substr(expand_region)
            
            match = re.match(r"\{([^\}]*)\}", content)
            match2 = re.match(r"[^\{]*", content)
            print expand_region
 
            rules = match.group(1).split(';')
            rules = filter(lambda r: r.strip(), rules)
            rules = ['\t' + r.strip() + ';\n' for r in rules]
            rules = ''.join(rules)
 
            view.replace(edit, expand_region, '{\n' + rules + '}')
 
    def rule_is_compact(self, rule):
        return re.match(r"^\{.*\}$", self.view.substr(rule))
