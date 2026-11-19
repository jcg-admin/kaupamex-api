"""El saneador de HTML de ``tools/mail.py``.

Porte de ``odoo19c: odoo/addons/base/tests/test_mail.py:26-547``
(``TestSanitizer`` y ``TestHtmlTools``; LGPL-3, Odoo S.A., con atribución).
Cambian los imports y la base de la clase (``BaseCase`` -> ``TestCase``).
Fuera: ``test_nl2br_enclose`` (``:472-494``), que prueba ``nl2br_enclose``
de ``ir.qweb`` y no un símbolo de esta unidad. Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
tools-mail-html-sanitizer.md``.
"""
import re
import unittest

from markupsafe import Markup

from tools import misc
from tools.mail import (
    append_content_to_html,
    html2plaintext,
    html_sanitize,
    html_to_inner_content,
    is_html_empty,
    plaintext2html,
    prepend_html_content,
)

from . import mail_examples


class TestSanitizer(unittest.TestCase):
    (
        ' Test the html sanitizer that filters html to remove unwanted '
        'attributes ')

    def test_abrupt_close(self):
        payload = """<!--> <script> alert(1) </script> -->"""
        html_result = html_sanitize(payload)
        self.assertNotIn('alert(1)', html_result)

        payload = """<!---> <script> alert(1) </script> -->"""
        html_result = html_sanitize(payload)
        self.assertNotIn('alert(1)', html_result)

    def test_abrut_malformed(self):
        payload = """<!--!> <script> alert(1) </script> -->"""
        html_result = html_sanitize(payload)
        self.assertNotIn('alert(1)', html_result)

        payload = """<!---!> <script> alert(1) </script> -->"""
        html_result = html_sanitize(payload)
        self.assertNotIn('alert(1)', html_result)

    def test_basic_sanitizer(self):
        cases = [
            ("yop", "<p>yop</p>"),  # simple
            ("lala<p>yop</p>xxx", "<p>lala</p><p>yop</p>xxx"),  # trailing text
            ((
                "Merci à l'intérêt pour notre produit.nous vous contacterons "
                'bientôt. Merci'),
                (
                    "<p>Merci à l'intérêt pour notre produit.nous vous "
                    'contacterons bientôt. Merci</p>')),  # unicode
            ('<div>a<div>b</div></div>', '<div>a<div>b</div></div>'),
            ('<div><div>a</div></div>', '<div><div>a</div></div>'),
            ('<script> alert(1) </script>', ''),
            ('<head><title>Title of the document</title><head>', ''),
        ]
        for content, expected in cases:
            html = html_sanitize(content)
            self.assertEqual(html, expected, 'html_sanitize is broken')
            html = html_sanitize(html)
            self.assertEqual(html, expected, 'html_sanitize is not idempotent')

    def test_comment_malformed(self):
        html = (
            "<!-- malformed-close --!> <img src='x' onerror='alert(1)'></img> "
            '--> comment <!-- normal comment --> --> out of context balise '
            '--!>')
        html_result = html_sanitize(html)
        self.assertNotIn('alert(1)', html_result)

    def test_comment_multiline(self):
        payload = """
            <div> <!--
                multi line comment
                --!> </div> <script> alert(1) </script> -->
        """
        html_result = html_sanitize(payload)
        self.assertNotIn('alert(1)', html_result)

    def test_evil_malicious_code(self):
        # taken from
        # https://www.owasp.org/index.php/XSS_Filter_Evasion_Cheat_Sheet#Tests
        cases = [
            ("<IMG SRC=javascript:alert('XSS')>"),  # no quotes and semicolons
            ((
                '<IMG SRC=&#106;&#97;&#118;&#97;&#115;&#99;&#114;&#105;&#112;&'
                '#116;&#58;&#97;&#108;&#101;&#114;&#116;&#40;&#39;&#88;&#83;&#'
                '83;&#39;&#41;>')),  # UTF-8 Unicode encoding
            ((
                '<IMG SRC=&#x6A&#x61&#x76&#x61&#x73&#x63&#x72&#x69&#x70&#x74&#'
                'x3A&#x61&#x6C&#x65&#x72&#x74&#x28&#x27&#x58&#x53&#x53&#x27&#x'
                '29>')),  # hex encoding
            ((
                # embedded carriage return
                '<IMG SRC="jav&#x0D;ascript:alert(\'XSS\');">')),
            ((
                # embedded newline
                '<IMG SRC="jav&#x0A;ascript:alert(\'XSS\');">')),
            ("<IMG SRC=\"jav   ascript:alert('XSS');\">"),  # embedded tab
            ((
                # embedded encoded tab
                '<IMG SRC="jav&#x09;ascript:alert(\'XSS\');">')),
            ((
                # spaces and meta-characters
                '<IMG SRC=" &#14;  javascript:alert(\'XSS\');">')),
            ("<IMG SRC=\"javascript:alert('XSS')\""),  # half-open html
            ((
                '<IMG """><SCRIPT>alert("XSS")</SCRIPT>">')),  # malformed tag
            ((
                # non-alpha-non-digits
                '<SCRIPT/XSS SRC="http://ha.ckers.org/xss.js"></SCRIPT>')),
            ((
                # non-alpha-non-digits
                '<SCRIPT/SRC="http://ha.ckers.org/xss.js"></SCRIPT>')),
            ((
                # extraneous open brackets
                '<<SCRIPT>alert("XSS");//<</SCRIPT>')),
            ((
                # non-closing script tags
                '<SCRIPT SRC=http://ha.ckers.org/xss.js?< B >')),
            ((
                # input image
                '<INPUT TYPE="IMAGE" SRC="javascript:alert(\'XSS\');">')),
            ("<BODY BACKGROUND=\"javascript:alert('XSS')\">"),  # body image
            ("<IMG DYNSRC=\"javascript:alert('XSS')\">"),  # img dynsrc
            ("<IMG LOWSRC=\"javascript:alert('XSS')\">"),  # img lowsrc
            ("<TABLE BACKGROUND=\"javascript:alert('XSS')\">"),  # table
            ("<TABLE><TD BACKGROUND=\"javascript:alert('XSS')\">"),  # td
            ((
                '<DIV STYLE="background-image: '
                'url(javascript:alert(\'XSS\'))">')),  # div background
            ((
                '<DIV STYLE="background-image:\x075\x072\x06C\x028\'\x06a\x061'
                '\x076\x061\x073\x063\x072\x069\x070\x074\x03a\x061\x06c\x065'
                # div background with unicoded exploit
                '\x072\x074\x028.1027\x058.1053\x053\x027\x029\'\x029">')),
            ((
                '<DIV STYLE="background-image: '
                # div background + extra characters
                'url(&#1;javascript:alert(\'XSS\'))">')),
            ("<IMG SRC='vbscript:msgbox(\"XSS\")'>"),  # VBscrip in an image
            ("<BODY ONLOAD=alert('XSS')>"),  # event handler
            ("<BR SIZE=\"&{alert('XSS')}\\>"),  # & javascript includes
            ((
                # style sheet
                '<LINK REL="stylesheet" HREF="javascript:alert(\'XSS\');">')),
            ((
                # remote style sheet
                '<LINK REL="stylesheet" HREF="http://ha.ckers.org/xss.css">')),
            ((
                # remote style sheet 2
                "<STYLE>@import'http://ha.ckers.org/xss.css';</STYLE>")),
            ((
                '<META HTTP-EQUIV="Link" Content="<http://ha.ckers.org/xss.css'
                '>; REL=stylesheet">')),  # remote style sheet 3
            ((
                '<STYLE>BODY{-moz-binding:url("http://ha.ckers.org/xssmoz.xml#'
                'xss")}</STYLE>')),  # remote style sheet 4
            ((
                # style attribute using a comment to break up expression
                '<IMG STYLE="xss:expr/*XSS*/ession(alert(\'XSS\'))">')),
        ]
        for content in cases:
            html = html_sanitize(content)
            self.assertNotIn((
                'javascript'), html, (
                'html_sanitize did not remove a malicious javascript'))
            self.assertTrue((
                'ha.ckers.org') not in html or (
                'http://ha.ckers.org/xss.css') in html, (
                'html_sanitize did not remove a malicious code in %s (%s)') % (
                    content, html))

        content = (
            # down-level hidden block
            "<!--[if gte IE 4]><SCRIPT>alert('XSS');</SCRIPT><![endif]-->")
        self.assertEqual(html_sanitize(content, silent=False), '')

    def test_html(self):
        sanitized_html = html_sanitize(mail_examples.MISC_HTML_SOURCE)
        for tag in ['<div', '<b', '<i', '<u', '<strike', '<li', '<blockquote',
                    '<a href']:
            self.assertIn(tag, sanitized_html, (
                'html_sanitize stripped too much of original html'))
        for attr in ['javascript']:
            self.assertNotIn(attr, sanitized_html, (
                'html_sanitize did not remove enough unwanted attributes'))

    def test_outlook_mail_sanitize(self):
        case = (
            '<div class="WordSection1">\n<p class="MsoNormal">Here is a test '
            'mail<o:p></o:p></p>\n<p class="MsoNormal"><o:p>&nbsp;</o:p></p>\n'
            '<p class="MsoNormal">With a break line<o:p></o:p></p>\n<p '
            'class="MsoNormal"><o:p>&nbsp;</o:p></p>\n<p '
            'class="MsoNormal"><o:p>&nbsp;</o:p></p>\n<p '
            'class="MsoNormal">Then two<o:p></o:p></p>\n<p '
            'class="MsoNormal"><o:p>&nbsp;</o:p></p>\n<div>\n<div '
            'style="border:none;border-top:solid #E1E1E1 1.0pt;padding:3.0pt '
            '0in 0in 0in">\n<p class="MsoNormal"><b>From:</b> Mitchell Admin '
            '&lt;dummy@example.com&gt;\n<br>\n<b>Sent:</b> Monday, November '
            '20, 2023 8:34 AM<br>\n<b>To:</b> test user '
            '&lt;dummy@example.com&gt;<br>\n<b>Subject:</b> test '
            '(#23)<o:p></o:p></p>\n</div>\n</div>')

        expected = (
            '<div class="WordSection1">\n<p class="MsoNormal">Here is a test '
            'mail</p>\n<p class="MsoNormal">&nbsp;</p>\n<p '
            'class="MsoNormal">With a break line</p>\n<p '
            'class="MsoNormal">&nbsp;</p>\n<p class="MsoNormal">&nbsp;</p>\n'
            '<p class="MsoNormal">Then two</p>\n<p '
            'class="MsoNormal">&nbsp;</p>\n<div>\n<div '
            'style="border:none;border-top:solid #E1E1E1 1.0pt;padding:3.0pt '
            '0in 0in 0in">\n<p class="MsoNormal"><b>From:</b> Mitchell Admin '
            '&lt;dummy@example.com&gt;\n<br>\n<b>Sent:</b> Monday, November '
            '20, 2023 8:34 AM<br>\n<b>To:</b> test user '
            '&lt;dummy@example.com&gt;<br>\n<b>Subject:</b> test (#23)</p>\n'
            '</div>\n</div></div>')

        result = html_sanitize(case)
        self.assertEqual(result, expected)

    def test_sanitize_unescape_emails(self):
        not_emails = [
            (
                '<blockquote cite="mid:CAEJSRZvWvud8c6Qp=wfNG6O1+wK3i_jb33qVrF'
                '7XyrgPNjnyUA@mail.gmail.com" type="cite">cat</blockquote>'),
            (
                '<img alt="@github-login" class="avatar" src="/web/image/pi" '
                'height="36" width="36">')]
        for not_email in not_emails:
            sanitized = html_sanitize(not_email)
            left_part = not_email.split((
                # take only left part, as the sanitizer could add data
                # information on node
                '>'))[0]
            self.assertNotIn(misc.html_escape(not_email), sanitized, (
                'html_sanitize stripped emails of original html'))
            self.assertIn(left_part, sanitized)

    def test_style_parsing(self):
        test_data = [
            (
                (
                    '<span style="position: fixed; top: 0px; left: 50px; '
                    'width: 40%; height: 50%; background-color: red;">Coin '
                    'coin </span>'),
                ['background-color:red', 'Coin coin'],
                ['position', 'top', 'left']
            ), (
                (
                    '<div style=\'before: "Email Address; coincoin cheval: '
                    'lapin";  \n   font-size: 30px; max-width: 100%; after: '
                    '"Not sure\n    \n          this; means: anything ?#ùµ"\n '
                    "   ; some-property: 2px; top: 3'>youplaboum</div>"),
                ['font-size:30px', 'youplaboum'],
                ['some-property', 'top', 'cheval']
            ), (
                '<span style="width">Coincoin</span>',
                [],
                ['width']
            )
        ]

        for test, in_lst, out_lst in test_data:
            new_html = html_sanitize(
                test, sanitize_attributes=False, sanitize_style=True,
                strip_style=False, strip_classes=False)
            for text in in_lst:
                self.assertIn(text, new_html)
            for text in out_lst:
                self.assertNotIn(text, new_html)

        # style should not be sanitized if removed
        new_html = html_sanitize(
            test_data[0][0], sanitize_attributes=False, strip_style=True,
            strip_classes=False)
        self.assertEqual(new_html, u'<span>Coin coin </span>')

    def test_style_class(self):
        html = html_sanitize(
            mail_examples.REMOVE_CLASS, sanitize_attributes=True,
            sanitize_style=True, strip_classes=True)
        for ext in mail_examples.REMOVE_CLASS_IN:
            self.assertIn(ext, html)
        for ext in mail_examples.REMOVE_CLASS_OUT:
            self.assertNotIn(ext, html,)

    def test_style_class_only(self):
        html = html_sanitize(
            mail_examples.REMOVE_CLASS, sanitize_attributes=False,
            sanitize_style=True, strip_classes=True)
        for ext in mail_examples.REMOVE_CLASS_IN:
            self.assertIn(ext, html)
        for ext in mail_examples.REMOVE_CLASS_OUT:
            self.assertNotIn(ext, html,)

    def test_edi_source(self):
        html = html_sanitize(mail_examples.EDI_LIKE_HTML_SOURCE)
        self.assertIn(
            (
                "font-family: 'Lucida Grande', Ubuntu, Arial, Verdana, "
                'sans-serif;'), html,
            'html_sanitize removed valid styling')
        self.assertIn(
            (
                'src="https://www.paypal.com/en_US/i/btn/'
                'btn_paynowCC_LG.gif"'),
            html,
            'html_sanitize removed valid img')
        self.assertNotIn((
            '</body></html>'), html, (
            'html_sanitize did not remove extra closing tags'))

    def test_quote_blockquote(self):
        html = html_sanitize(mail_examples.QUOTE_BLOCKQUOTE)
        for ext in mail_examples.QUOTE_BLOCKQUOTE_IN:
            self.assertIn(ext, html)
        for ext in mail_examples.QUOTE_BLOCKQUOTE_OUT:
            self.assertIn((
                '<span data-o-mail-quote="1">%s') % (
                    misc.html_escape(ext)), html)

    def test_quote_thunderbird(self):
        html = html_sanitize(mail_examples.QUOTE_THUNDERBIRD_1)
        for ext in mail_examples.QUOTE_THUNDERBIRD_1_IN:
            self.assertIn(ext, html)
        for ext in mail_examples.QUOTE_THUNDERBIRD_1_OUT:
            self.assertIn((
                '<span data-o-mail-quote="1">%s</span>') % (
                    misc.html_escape(ext)), html)

    def test_quote_hotmail_html(self):
        html = html_sanitize(mail_examples.QUOTE_HOTMAIL_HTML)
        for ext in mail_examples.QUOTE_HOTMAIL_HTML_IN:
            self.assertIn(ext, html)
        for ext in mail_examples.QUOTE_HOTMAIL_HTML_OUT:
            self.assertIn(ext, html)

        html = html_sanitize(mail_examples.HOTMAIL_1)
        for ext in mail_examples.HOTMAIL_1_IN:
            self.assertIn(ext, html)
        for ext in mail_examples.HOTMAIL_1_OUT:
            self.assertIn(ext, html)

    def test_quote_outlook_html(self):
        html = html_sanitize(mail_examples.QUOTE_OUTLOOK_HTML)
        for ext in mail_examples.QUOTE_OUTLOOK_HTML_IN:
            self.assertIn(ext, html)
        for ext in mail_examples.QUOTE_OUTLOOK_HTML_OUT:
            self.assertIn(ext, html)

    def test_quote_thunderbird_html(self):
        html = html_sanitize(mail_examples.QUOTE_THUNDERBIRD_HTML)
        for ext in mail_examples.QUOTE_THUNDERBIRD_HTML_IN:
            self.assertIn(ext, html)
        for ext in mail_examples.QUOTE_THUNDERBIRD_HTML_OUT:
            self.assertIn(ext, html)

    def test_quote_yahoo_html(self):
        html = html_sanitize(mail_examples.QUOTE_YAHOO_HTML)
        for ext in mail_examples.QUOTE_YAHOO_HTML_IN:
            self.assertIn(ext, html)
        for ext in mail_examples.QUOTE_YAHOO_HTML_OUT:
            self.assertIn(ext, html)

    def test_quote_basic_text(self):
        test_data = [
            (
                """This is Sparta!\n--\nAdministrator\n+9988776655""",
                ['This is Sparta!'],
                ['\n--\nAdministrator\n+9988776655']
            ), (
                """<p>This is Sparta!\n--\nAdministrator</p>""",
                [],
                ['\n--\nAdministrator']
            ), (
                """<p>This is Sparta!<br/>--<br>Administrator</p>""",
                ['This is Sparta!'],
                []
            ), (
                """This is Sparta!\n>Ah bon ?\nCertes\n> Chouette !\nClair""",
                ['This is Sparta!', 'Certes', 'Clair'],
                ['\n>Ah bon ?', '\n> Chouette !']
            )
        ]
        for test, in_lst, out_lst in test_data:
            new_html = html_sanitize(test)
            for text in in_lst:
                self.assertIn(text, new_html)
            for text in out_lst:
                self.assertIn((
                    '<span data-o-mail-quote="1">%s</span>') % (
                        misc.html_escape(text)), new_html)

    def test_quote_signature(self):
        test_data = [
            (
                """<div>Hello<pre>--<br />Administrator</pre></div>""",
                [(
                    '<pre data-o-mail-quote="1">--'), (
                    '<br data-o-mail-quote="1">')],
            )
        ]
        for test, in_lst in test_data:
            new_html = html_sanitize(test)
            for text in in_lst:
                self.assertIn(text, new_html)

    def test_quote_signature_container_propagation(self):
        (
            "Test that applying normalization twice doesn't quote more than "
            'wanted.')
        # quote signature with bare signature in main block
        bare_signature_body = (
            "<div>"
            "<div><p>Hello</p><p>Here is your document</p></div>"
            "<div>--<br>Mark Demo</div>"
            "<div class=\"bg-300\"></div>"
            "</div>"
        )
        expected_result = (
            (
                '<div data-o-mail-quote-container="1"><div><p>Hello</p><p>Here'
                ' is your document</p></div><div data-o-mail-quote="1">--<br '
                'data-o-mail-quote="1">Mark Demo</div><div class="bg-300" '
                'data-o-mail-quote="1"></div></div>')
        )
        sanitized_once = html_sanitize(bare_signature_body)
        sanitized_twice = html_sanitize(sanitized_once)
        self.assertEqual(sanitized_once, expected_result)
        self.assertEqual(sanitized_twice, expected_result)

    def test_quote_gmail(self):
        html = html_sanitize(mail_examples.GMAIL_1)
        for ext in mail_examples.GMAIL_1_IN:
            self.assertIn(ext, html)
        for ext in mail_examples.GMAIL_1_OUT:
            self.assertIn((
                '<span data-o-mail-quote="1">%s</span>') % (
                    misc.html_escape(ext)), html)

    def test_quote_text(self):
        html = html_sanitize(mail_examples.TEXT_1)
        for ext in mail_examples.TEXT_1_IN:
            self.assertIn(ext, html)
        for ext in mail_examples.TEXT_1_OUT:
            self.assertIn((
                '<span data-o-mail-quote="1">%s</span>') % (
                    misc.html_escape(ext)), html)

        html = html_sanitize(mail_examples.TEXT_2)
        for ext in mail_examples.TEXT_2_IN:
            self.assertIn(ext, html)
        for ext in mail_examples.TEXT_2_OUT:
            self.assertIn((
                '<span data-o-mail-quote="1">%s</span>') % (
                    misc.html_escape(ext)), html)

    def test_quote_bugs(self):
        html = html_sanitize(mail_examples.BUG1)
        for ext in mail_examples.BUG_1_IN:
            self.assertIn(ext, html)
        for ext in mail_examples.BUG_1_OUT:
            self.assertIn((
                '<span data-o-mail-quote="1">%s</span>') % (
                    misc.html_escape(ext)), html)

    def test_misc(self):
        # False / void should not crash
        html = html_sanitize('')
        self.assertEqual(html, '')
        html = html_sanitize(False)
        self.assertEqual(html, False)

        # Message with xml and doctype tags don't crash
        html = html_sanitize((
            '<?xml version="1.0" encoding="iso-8859-1"?>\n<!DOCTYPE html '
            'PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"\n         '
            '"http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">\n'
            '<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" '
            'lang="en">\n <head>\n  <title>404 - Not Found</title>\n </head>\n'
            ' <body>\n  <h1>404 - Not Found</h1>\n </body>\n</html>\n'))
        self.assertNotIn('encoding', html)
        self.assertNotIn('<title>404 - Not Found</title>', html)
        self.assertIn('<h1>404 - Not Found</h1>', html)

    def test_cid_with_at(self):
        img_tag = '<img src="@">'
        sanitized = html_sanitize(
            img_tag, sanitize_tags=False, strip_classes=True)
        self.assertEqual(img_tag, sanitized, (
            "img with can have cid containing @ and shouldn't be escaped"))

    # ms office is currently not supported, have to find a way to support it
    # def test_30_email_msoffice(self):
    #     new_html = html_sanitize(mail_examples.MSOFFICE_1, remove=True)
    #     for ext in mail_examples.MSOFFICE_1_IN:
    #         self.assertIn(ext, new_html)
    #     for ext in mail_examples.MSOFFICE_1_OUT:
    #         self.assertNotIn(ext, new_html)


class TestHtmlTools(unittest.TestCase):
    """ Test some of our generic utility functions about html """

    def test_plaintext2html(self):
        cases = [
            ((
                'First \nSecond \nThird\n \nParagraph\n\r--\nSignature '
                'paragraph'), (
                'div'), True,
             (
                 '<div><p>First <br/>Second <br/>Third</p><p>Paragraph</p><p>-'
                 '-<br/>Signature paragraph</p></div>')),
            ("First<p>It should be escaped</p>\nSignature", False, True,
             (
                 '<p>First&lt;p&gt;It should be escaped&lt;/p&gt;<br/>Signatur'
                 'e</p>')),
            ("First \nSecond \nThird", False, False,
             "First <br/>Second <br/>Third"),
        ]
        for content, container_tag, with_paragraph, expected in cases:
            html = plaintext2html(content, container_tag, with_paragraph)
            self.assertEqual(html, expected, 'plaintext2html is broken')

    def test_html_html_to_inner_content(self):
        cases = [
            ((
                '<div><p>First <br/>Second <br/>Third '
                'Paragraph</p><p>--<br/>Signature paragraph with a <a '
                'href="./link">link</a></p></div>'),
             (
                 'First Second Third Paragraph -- Signature paragraph with a '
                 'link')),
            ((
                '<p>Now =&gt; processing&nbsp;entities&#8203;and extra '
                'whitespace too.  </p>'),
             'Now => processing\xa0entities\u200band extra whitespace too.'),
            ((
                '<div>Look what happens with <p>unmatched tags</div>'), (
                'Look what happens with unmatched tags')),
            ((
                '<div>Look what happens with <p unclosed tags</div> Are we '
                'good?'), (
                'Look what happens with Are we good?'))
        ]
        for content, expected in cases:
            text = html_to_inner_content(content)
            self.assertEqual(text, expected, (
                'html_html_to_inner_content is broken'))

    def test_append_to_html(self):
        test_samples = [
            ((
                '<!DOCTYPE...><HTML encoding="blah">some <b>content</b>'
                '</HtMl>'), (
                '--\nYours truly'), True, True, False,
             (
                 '<!DOCTYPE...><html encoding="blah">some <b>content</b>\n'
                 '<pre>--\nYours truly</pre>\n</html>')),
            ((
                '<!DOCTYPE...><HTML encoding="blah">some <b>content</b>'
                '</HtMl>'), (
                '--\nYours truly'), True, False, False,
             (
                 '<!DOCTYPE...><html encoding="blah">some <b>content</b>\n'
                 '<p>--<br/>Yours truly</p>\n</html>')),
            ((
                '<html><body>some <b>content</b></body></html>'), (
                '--\nYours & <truly>'), True, True, False,
             (
                 '<html><body>some <b>content</b>\n<pre>--\nYours &amp; '
                 '&lt;truly&gt;</pre>\n</body></html>')),
            ((
                '<html><body>some <b>content</b></body></html>'), (
                '<!DOCTYPE...>\n<html><body>\n<p>--</p>\n<p>Yours truly</p>\n'
                '</body>\n</html>'), False, False, False,
             (
                 '<html><body>some <b>content</b>\n\n\n<p>--</p>\n<p>Yours '
                 'truly</p>\n\n\n</body></html>')),
        ]
        for (html, content, plaintext_flag, preserve_flag, container_tag,
             expected) in test_samples:
            self.assertEqual(append_content_to_html(
                html, content, plaintext_flag, preserve_flag, container_tag),
                expected, (
                'append_content_to_html is broken'))

    def test_is_html_empty(self):
        void_strings_samples = ['', False, ' ']
        for content in void_strings_samples:
            self.assertTrue(is_html_empty(content))

        void_html_samples = [
            '<section><br /> <b><i/></b></section>',
            '<section><br /> <b><i/ ></b></section>',
            '<section><br /> <b>< i/ ></b></section>',
            '<section><br /> <b>< i / ></b></section>',
            '<p><br></p>', '<p><br> </p>', '<p><br /></p >',
            '<p style="margin: 4px"></p>',
            '<div style="margin: 4px"></div>',
            '<p class="oe_testing"><br></p>',
            (
                '<p><span style="font-weight: bolder;"><font style="color: '
                'rgb(255, 0, 0);" class=" "></font></span><br></p>'),
        ]
        for content in void_html_samples:
            self.assertTrue(is_html_empty(content), 'Failed with %s' % content)

        valid_html_samples = [
            (
                '<p><br>1</p>'), (
                '<p>1<br > </p>'), (
                '<p style="margin: 4px">Hello World</p>'),
            '<div style="margin: 4px"><p>Hello World</p></div>',
            (
                '<p><span style="font-weight: bolder;"><font style="color: '
                'rgb(255, 0, 0);" class=" ">W</font></span><br></p>'),
            '<span class="fa fa-heart"></span>',
            '<i class="fas fa-home"></i>'
        ]
        for content in valid_html_samples:
            self.assertFalse(is_html_empty(content))

    def test_prepend_html_content(self):
        body = """
            <html>
                <body>
                    <div>test</div>
                </body>
            </html>
        """

        content = "<span>content</span>"

        result = prepend_html_content(body, content)
        result = re.sub(r'[\s\t]', '', result)
        self.assertEqual(result, (
            '<html><body><span>content</span><div>test</div></body></html>'))

        body = "<div>test</div>"
        content = "<span>content</span>"

        result = prepend_html_content(body, content)
        result = re.sub(r'[\s\t]', '', result)
        self.assertEqual(result, "<span>content</span><div>test</div>")

        body = """
            <body>
                <div>test</div>
            </body>
        """

        result = prepend_html_content(body, content)
        result = re.sub(r'[\s\t]', '', result)
        self.assertEqual(result, (
            '<body><span>content</span><div>test</div></body>'))

        body = """
            <html>
                <body>
                    <div>test</div>
                </body>
            </html>
        """

        content = """
            <html>
                <body>
                    <div>test</div>
                </body>
            </html>
        """
        result = prepend_html_content(body, content)
        result = re.sub(r'[\s\t]', '', result)
        self.assertEqual(result, (
            '<html><body><div>test</div><div>test</div></body></html>'))
