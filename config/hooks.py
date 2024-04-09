import json  # TODO: remove
import logging
import netrc
import os
import pprint # TODO: remove
import re
import subprocess
import time
import urllib.parse

from bs4 import BeautifulSoup
import requests
from urlwatch import filters
from urlwatch import reporters
from urlwatch.mailer import SMTPMailer
from urlwatch.mailer import SendmailMailer

logger = logging.getLogger(__name__)

TEST_HTML = """

<html>
<body>
<h2><span class="verb">changed:</span> <a href="https://housing.sanjoseca.gov/listing/3b374f00-628a-4886-ad74-691835d74af7/mesa_terrace_1171_mesa_drive_san_jose_ca">https://housing.sanjoseca.gov/listing/3b374f00-628a-4886-ad74-691835d74af7/mesa_terrace_1171_mesa_drive_san_jose_ca</a></h2>

    <table class="diff" id="difflib_chg_to9__top"
           cellspacing="0" cellpadding="0" rules="groups" >
        <colgroup></colgroup> <colgroup></colgroup> <colgroup></colgroup>
        <colgroup></colgroup> <colgroup></colgroup> <colgroup></colgroup>
        <thead><tr><th class="diff_next"><br /></th><th colspan="2" class="diff_header">Fri, 01 Mar 2024 13:08:03 -0800</th><th class="diff_next"><br /></th><th colspan="2" class="diff_header">Thu, 04 Apr 2024 06:10:26 -0700</th></tr></thead>
        <tbody>
            <tr><td class="diff_next" id="difflib_chg_to9__0"></td><td class="diff_header" id="from9_22">22</td><td nowrap="nowrap"></td><td class="diff_next"></td><td class="diff_header" id="to9_22">22</td><td nowrap="nowrap"></td></tr>
            <tr><td class="diff_next"></td><td class="diff_header" id="from9_23">23</td><td nowrap="nowrap">Unit&nbspnbsp;Type&nbsp;&nbsp;|&nbsp;Minimum&nbsp;Income&nbsp;&nbsp;|&nbsp;Rent&nbsp;&nbsp;|&nbsp;Availability&nbsp;&nbsp;</td><td class="diff_next"></td><td class="diff_header" id="to9_23">23</td><td nowrap="nowrap">Unit&nbsp;Type&nbsp;&nbsp;|&nbsp;Minimum&nbsp;Income&nbsp;&nbsp;|&nbsp;Rent&nbsp;&nbsp;|&nbsp;Availability&nbsp;&nbsp;</td></tr>
            <tr><td class="diff_next" id="difflib_chg_to9__1"></td><td class="diff_header" id="from9_24">24</td><td nowrap="nowrap">---|---|---|---&nbsp;&nbsp;</td><td class="diff_next"></td><td class="diff_header" id="to9_24">24</td><td nowrap="nowrap">---|---|---|---&nbsp;&nbsp;</td></tr>
            <tr><td class="diff_next"><a href="#difflib_chg_to9__1">n</a></td><td class="diff_header" id="from9_25">25</td><td nowrap="nowrap">**1&nbsp;BR**&nbsp;|&nbsp;**$3,370**&nbsp;per&nbsp;month&nbsp;|&nbsp;**$1,685**&nbsp;per&nbsp;month&nbsp;|&nbsp;**<span class="diff_chg">Ope</span>n<span class="diff_chg">&nbsp;Wa</span>it<span class="diff_sub">li</span>s<span class="diff_chg">t**&nbsp;&nbsp;</span></td><td class="diff_next"><a href="#difflib_chg_to9__1">n</a></td><td class="diff_header" id="to9_25">25</td><td nowrap="nowrap">**1&nbsp;BR**&nbsp;|&nbsp;**$3,370**&nbsp;per&nbsp;month&nbsp;|&nbsp;**$1,685**&nbsp;per&nbsp;month&nbsp;|&nbsp;**<span class="diff_chg">2**&nbsp;Vaca</span>n<span class="diff_chg">t&nbsp;Un</span>its<span class="diff_chg">&nbsp;&nbsp;</span></td></tr>
            <tr><td class="diff_next"></td><td class="diff_header" id="from9_26">26</td><td nowrap="nowrap">&nbsp;&nbsp;</td><td class="diff_next"></td><td class="diff_header" id="to9_26">26</td><td nowrap="nowrap">&nbsp;&nbsp;</td></tr>
            <tr><td class="diff_next" id="difflib_chg_to9__2"><a href="#difflib_chg_to9__2">n</a></td><td class="diff_header"></td><td nowrap="nowrap"></td><td class="diff_next"><a href="#difflib_chg_to9__2">n</a></td><td class="diff_header" id="to9_27">27</td><td nowrap="nowrap"><span class="diff_add">First&nbsp;Come&nbsp;First&nbsp;Serve&nbsp;&nbsp;</span></td></tr>
            <tr><td class="diff_next"></td><td class="diff_header" id="from9_27">27</td><td nowrap="nowrap">Applications&nbsp;Closed</td><td class="diff_next"></td><td class="diff_header" id="to9_28">28</td><td nowrap="nowrap">Applications&nbsp;Closed</td></tr>
            <tr><td class="diff_next" id="difflib_chg_to9__3"></td><td class="diff_header" id="from9_28">28</td><td nowrap="nowrap"></td><td class="diff_next"></td><td class="diff_header" id="to9_29">29</td><td nowrap="nowrap"></td></tr>
            <tr><td class="diff_next"><a href="#difflib_chg_to9__3">n</a></td><td class="diff_header" id="from9_29">29</td><td nowrap="nowrap"><span class="diff_sub">####&nbsp;Waitlist&nbsp;is&nbsp;open</span></td><td class="diff_next"><a href="#difflib_chg_to9__3">n</a></td><td class="diff_header" id="to9_30">30</td><td nowrap="nowrap"><span class="diff_add">####&nbsp;Vacant&nbsp;Units&nbsp;Available</span></td></tr>
            <tr><td class="diff_next"></td><td class="diff_header" id="from9_30">30</td><td nowrap="nowrap"></td><td class="diff_next"></td><td class="diff_header" id="to9_31">31</td><td nowrap="nowrap"></td></tr>
            <tr><td class="diff_next"><a href="#difflib_chg_to9__4">n</a></td><td class="diff_header" id="from9_31">31</td><td nowrap="nowrap"><span class="diff_sub">Submit&nbsp;an&nbsp;application&nbsp;for&nbsp;an&nbsp;open&nbsp;slot&nbsp;on&nbsp;the&nbsp;waitlist.</span></td><td class="diff_next"><a href="#difflib_chg_to9__4">n</a></td><td class="diff_header" id="to9_32">32</td><td nowrap="nowrap"><span class="diff_add">Eligible&nbsp;applicants&nbsp;will&nbsp;be&nbsp;contacted&nbsp;on&nbsp;a&nbsp;first&nbsp;come&nbsp;first&nbsp;serve&nbsp;basis&nbsp;until</span></td></tr>
            <tr><td class="diff_next"></td><td class="diff_header"></td><td nowrap="nowrap"></td><td class="diff_next"></td><td class="diff_header" id="to9_33">33</td><td nowrap="nowrap"><span class="diff_add">vacancies&nbsp;are&nbsp;filled.</span></td></tr>
            <tr><td class="diff_next"></td><td class="diff_header"></td><td nowrap="nowrap"></td><td class="diff_next"></td><td class="diff_header" id="to9_34">34</td><td nowrap="nowrap"><span class="diff_add">&nbsp;</span></td></tr>
            <tr><td class="diff_next"></td><td class="diff_header"></td><td nowrap="nowrap"></td><td class="diff_next"></td><td class="diff_header" id="to9_35">35</td><td nowrap="nowrap"><span class="diff_add">&nbsp;&nbsp;*&nbsp;2Vacant&nbsp;Units</span></td></tr>
            <tr><td class="diff_next"></td><td class="diff_header" id="from9_32">32</td><td nowrap="nowrap"></td><td class="diff_next"></td><td class="diff_header" id="to9_36">36</td><td nowrap="nowrap"></td></tr>
            <tr><td class="diff_next"></td><td class="diff_header" id="from9_33">33</td><td nowrap="nowrap">&nbsp;&nbsp;*&nbsp;![Eligibility&nbsp;Notebook](https://housing.sanjoseca.gov/images/listing-eligibility.svg)</td><td class="diff_next"></td><td class="diff_header" id="to9_37">37</td><td nowrap="nowrap">&nbsp;&nbsp;*&nbsp;![Eligibility&nbsp;Notebook](https://housing.sanjoseca.gov/images/listing-eligibility.svg)</td></tr>
            <tr><td class="diff_next"></td><td class="diff_header" id="from9_34">34</td><td nowrap="nowrap"></td><td class="diff_next"></td><td class="diff_header" id="to9_38">38</td><td nowrap="nowrap"></td></tr>
        </tbody>
        <tbody>
            <tr><td class="diff_next" id="difflib_chg_to9__4"></td><td class="diff_header" id="from9_52">52</td><td nowrap="nowrap"></td><td class="diff_next"></td><td class="diff_header" id="to9_56">56</td><td nowrap="nowrap"></td></tr>
            <tr><td class="diff_next"></td><td class="diff_header" id="from9_53">53</td><td nowrap="nowrap">Household&nbsp;Size&nbsp;|&nbsp;Maximum&nbsp;Income&nbsp;/&nbsp;Month&nbsp;|&nbsp;Maximum&nbsp;Income&nbsp;/&nbsp;Year&nbsp;&nbsp;</td><td class="diff_next"></td><td class="diff_header" id="to9_57">57</td><td nowrap="nowrap">Household&nbsp;Size&nbsp;|&nbsp;Maximum&nbsp;Income&nbsp;/&nbsp;Month&nbsp;|&nbsp;Maximum&nbsp;Income&nbsp;/&nbsp;Year&nbsp;&nbsp;</td></tr>
            <tr><td class="diff_next"></td><td class="diff_header" id="from9_54">54</td><td nowrap="nowrap">---|---|---&nbsp;&nbsp;</td><td class="diff_next"></td><td class="diff_header" id="to9_58">58</td><td nowrap="nowrap">---|---|---&nbsp;&nbsp;</td></tr>
            <tr><td class="diff_next"><a href="#difflib_chg_to9__5">n</a></td><td class="diff_header" id="from9_55">55</td><td nowrap="nowrap">**1**&nbsp;|&nbsp;$4<span class="diff_sub">,917</span>&nbsp;per&nbsp;month&nbsp;|&nbsp;$5<span class="diff_sub">9,</span>0<span class="diff_sub">00</span>&nbsp;per&nbsp;year&nbsp;&nbsp;</td><td class="diff_next"><a href="#difflib_chg_to9__5">n</a></td><td class="diff_header" id="to9_59">59</td><td nowrap="nowrap">**1**&nbsp;|&nbsp;$<span class="diff_add">5,20</span>4&nbsp;per&nbsp;month&nbsp;|&nbsp;$<span class="diff_add">62,4</span>50&nbsp;per&nbsp;year&nbsp;&nbsp;</td></tr>
            <tr><td class="diff_next"></td><td class="diff_header" id="from9_56">56</td><td nowrap="nowrap">**2**&nbsp;|&nbsp;$5,<span class="diff_chg">617</span>&nbsp;per&nbsp;month&nbsp;|&nbsp;$<span class="diff_sub">6</span>7,400&nbsp;per&nbsp;year&nbsp;&nbsp;</td><td class="diff_next"></td><td class="diff_header" id="to9_60">60</td><td nowrap="nowrap">**2**&nbsp;|&nbsp;$5,<span class="diff_chg">950</span>&nbsp;per&nbsp;month&nbsp;|&nbsp;$7<span class="diff_add">1</span>,400&nbsp;per&nbsp;year&nbsp;&nbsp;</td></tr>
            <tr><td class="diff_next"></td><td class="diff_header" id="from9_57">57</td><td nowrap="nowrap">**3**&nbsp;|&nbsp;$6,<span class="diff_chg">3</span>2<span class="diff_sub">1</span>&nbsp;per&nbsp;month&nbsp;|&nbsp;$<span class="diff_chg">75</span>,<span class="diff_chg">85</span>0&nbsp;per&nbsp;year&nbsp;&nbsp;</td><td class="diff_next"></td><td class="diff_header" id="to9_61">61</td><td nowrap="nowrap">**3**&nbsp;|&nbsp;$6,<span class="diff_chg">69</span>2&nbsp;per&nbsp;month&nbsp;|&nbsp;$<span class="diff_chg">80</span>,<span class="diff_chg">3</span>0<span class="diff_add">0</span>&nbsp;per&nbsp;year&nbsp;&nbsp;</td></tr>
            <tr><td class="diff_next"></td><td class="diff_header" id="from9_58">58</td><td nowrap="nowrap">&nbsp;&nbsp;</td><td class="diff_next"></td><td class="diff_header" id="to9_62">62</td><td nowrap="nowrap">&nbsp;&nbsp;</td></tr>
            <tr><td class="diff_next"></td><td class="diff_header" id="from9_59">59</td><td nowrap="nowrap">&nbsp;&nbsp;&nbsp;&nbsp;*&nbsp;###&nbsp;Occupancy</td><td class="diff_next"></td><td class="diff_header" id="to9_63">63</td><td nowrap="nowrap">&nbsp;&nbsp;&nbsp;&nbsp;*&nbsp;###&nbsp;Occupancy</td></tr>
            <tr><td class="diff_next"></td><td class="diff_header" id="from9_60">60</td><td nowrap="nowrap"></td><td class="diff_next"></td><td class="diff_header" id="to9_64">64</td><td nowrap="nowrap"></td></tr>
        </tbody>
        <tbody>
            <tr><td class="diff_next" id="difflib_chg_to9__5"></td><td class="diff_header" id="from9_77">77</td><td nowrap="nowrap"></td><td class="diff_next"></td><td class="diff_header" id="to9_81">81</td><td nowrap="nowrap"></td></tr>
            <tr><td class="diff_next"></td><td class="diff_header" id="from9_78">78</td><td nowrap="nowrap">Important&nbsp;dates&nbsp;and&nbsp;contact&nbsp;information</td><td class="diff_next"></td><td class="diff_header" id="to9_82">82</td><td nowrap="nowrap">Important&nbsp;dates&nbsp;and&nbsp;contact&nbsp;information</td></tr>
            <tr><td class="diff_next"></td><td class="diff_header" id="from9_79">79</td><td nowrap="nowrap"></td><td class="diff_next"></td><td class="diff_header" id="to9_83">83</td><td nowrap="nowrap"></td></tr>
            <tr><td class="diff_next" id="difflib_chg_to9__6"><a href="#difflib_chg_to9__6">n</a></td><td class="diff_header"></td><td nowrap="nowrap"></td><td class="diff_next"><a href="#difflib_chg_to9__6">n</a></td><td class="diff_header" id="to9_84">84</td><td nowrap="nowrap"><span class="diff_add">First&nbsp;Come&nbsp;First&nbsp;Serve&nbsp;&nbsp;</span></td></tr>
            <tr><td class="diff_next"></td><td class="diff_header" id="from9_80">80</td><td nowrap="nowrap">Applications&nbsp;Closed</td><td class="diff_next"></td><td class="diff_header" id="to9_85">85</td><td nowrap="nowrap">Applications&nbsp;Closed</td></tr>
            <tr><td class="diff_next" id="difflib_chg_to9__7"></td><td class="diff_header" id="from9_81">81</td><td nowrap="nowrap"></td><td class="diff_next"></td><td class="diff_header" id="to9_86">86</td><td nowrap="nowrap"></td></tr>
            <tr><td class="diff_next"><a href="#difflib_chg_to9__7">n</a></td><td class="diff_header" id="from9_82">82</td><td nowrap="nowrap"><span class="diff_sub">####&nbsp;Waitlist&nbsp;is&nbsp;open</span></td><td class="diff_next"><a href="#difflib_chg_to9__7">n</a></td><td class="diff_header" id="to9_87">87</td><td nowrap="nowrap"><span class="diff_add">####&nbsp;Vacant&nbsp;Units&nbsp;Available</span></td></tr>
            <tr><td class="diff_next"></td><td class="diff_header" id="from9_83">83</td><td nowrap="nowrap"></td><td class="diff_next"></td><td class="diff_header" id="to9_88">88</td><td nowrap="nowrap"></td></tr>
            <tr><td class="diff_next"><a href="#difflib_chg_to9__8">n</a></td><td class="diff_header" id="from9_84">84</td><td nowrap="nowrap"><span class="diff_sub">Submit&nbsp;an&nbsp;application&nbsp;for&nbsp;an&nbsp;open&nbsp;slot&nbsp;on&nbsp;the&nbsp;waitlist.</span></td><td class="diff_next"><a href="#difflib_chg_to9__8">n</a></td><td class="diff_header" id="to9_89">89</td><td nowrap="nowrap"><span class="diff_add">Eligible&nbsp;applicants&nbsp;will&nbsp;be&nbsp;contacted&nbsp;on&nbsp;a&nbsp;first&nbsp;come&nbsp;first&nbsp;serve&nbsp;basis&nbsp;until</span></td></tr>
            <tr><td class="diff_next"></td><td class="diff_header"></td><td nowrap="nowrap"></td><td class="diff_next"></td><td class="diff_header" id="to9_90">90</td><td nowrap="nowrap"><span class="diff_add">vacancies&nbsp;are&nbsp;filled.</span></td></tr>
            <tr><td class="diff_next"></td><td class="diff_header"></td><td nowrap="nowrap"></td><td class="diff_next"></td><td class="diff_header" id="to9_91">91</td><td nowrap="nowrap"><span class="diff_add">&nbsp;</span></td></tr>
            <tr><td class="diff_next"></td><td class="diff_header"></td><td nowrap="nowrap"></td><td class="diff_next"></td><td class="diff_header" id="to9_92">92</td><td nowrap="nowrap"><span class="diff_add">&nbsp;&nbsp;&nbsp;&nbsp;*&nbsp;2Vacant&nbsp;Units</span></td></tr>
            <tr><td class="diff_next"></td><td class="diff_header" id="from9_85">85</td><td nowrap="nowrap"></td><td class="diff_next"></td><td class="diff_header" id="to9_93">93</td><td nowrap="nowrap"></td></tr>
            <tr><td class="diff_next"></td><td class="diff_header" id="from9_86">86</td><td nowrap="nowrap">##&nbsp;For&nbsp;further&nbsp;information</td><td class="diff_next"></td><td class="diff_header" id="to9_94">94</td><td nowrap="nowrap">##&nbsp;For&nbsp;further&nbsp;information</td></tr>
            <tr><td class="diff_next"></td><td class="diff_header" id="from9_87">87</td><td nowrap="nowrap"></td><td class="diff_next"></td><td class="diff_header" id="to9_95">95</td><td nowrap="nowrap"></td></tr>
        </tbody>
        <tbody>
            <tr><td class="diff_next" id="difflib_chg_to9__8"></td><td class="diff_header" id="from9_134">134</td><td nowrap="nowrap">Built</td><td class="diff_next"></td><td class="diff_header" id="to9_142">142</td><td nowrap="nowrap">Built</td></tr>
            <tr><td class="diff_next"></td><td class="diff_header" id="from9_135">135</td><td nowrap="nowrap"></td><td class="diff_next"></td><td class="diff_header" id="to9_143">143</td><td nowrap="nowrap"></td></tr>
            <tr><td class="diff_next"></td><td class="diff_header" id="from9_136">136</td><td nowrap="nowrap">&nbsp;&nbsp;&nbsp;&nbsp;2022</td><td class="diff_next"></td><td class="diff_header" id="to9_144">144</td><td nowrap="nowrap">&nbsp;&nbsp;&nbsp;&nbsp;2022</td></tr>
            <tr><td class="diff_next"><a href="#difflib_chg_to9__9">n</a></td><td class="diff_header"></td><td nowrap="nowrap"></td><td class="diff_next"><a href="#difflib_chg_to9__9">n</a></td><td class="diff_header" id="to9_145">145</td><td nowrap="nowrap"><span class="diff_add">Smoking&nbsp;Policy</span></td></tr>
            <tr><td class="diff_next"></td><td class="diff_header"></td><td nowrap="nowrap"></td><td class="diff_next"></td><td class="diff_header" id="to9_146">146</td><td nowrap="nowrap"><span class="diff_add">&nbsp;</span></td></tr>
            <tr><td class="diff_next"></td><td class="diff_header"></td><td nowrap="nowrap"></td><td class="diff_next"></td><td class="diff_header" id="to9_147">147</td><td nowrap="nowrap"><span class="diff_add">&nbsp;&nbsp;&nbsp;&nbsp;Non-Smoking&nbsp;Property</span></td></tr>
            <tr><td class="diff_next"></td><td class="diff_header"></td><td nowrap="nowrap"></td><td class="diff_next"></td><td class="diff_header" id="to9_148">148</td><td nowrap="nowrap"><span class="diff_add">Pets&nbsp;Policy</span></td></tr>
            <tr><td class="diff_next"></td><td class="diff_header"></td><td nowrap="nowrap"></td><td class="diff_next"></td><td class="diff_header" id="to9_149">149</td><td nowrap="nowrap"><span class="diff_add">&nbsp;</span></td></tr>
            <tr><td class="diff_next"></td><td class="diff_header"></td><td nowrap="nowrap"></td><td class="diff_next"></td><td class="diff_header" id="to9_150">150</td><td nowrap="nowrap"><span class="diff_add">&nbsp;&nbsp;&nbsp;&nbsp;Maximum&nbsp;of&nbsp;2&nbsp;pets&nbsp;allowed&nbsp;with&nbsp;an&nbsp;additional&nbsp;pet&nbsp;deposit&nbsp;of&nbsp;$300&nbsp;per&nbsp;pet&nbsp;due&nbsp;at&nbsp;move.</span></td></tr>
            <tr><td class="diff_next"></td><td class="diff_header" id="from9_137">137</td><td nowrap="nowrap">Property&nbsp;Amenities</td><td class="diff_next"></td><td class="diff_header" id="to9_151">151</td><td nowrap="nowrap">Property&nbsp;Amenities</td></tr>
            <tr><td class="diff_next"></td><td class="diff_header" id="from9_138">138</td><td nowrap="nowrap"></td><td class="diff_next"></td><td class="diff_header" id="to9_152">152</td><td nowrap="nowrap"></td></tr>
            <tr><td class="diff_next"></td><td class="diff_header" id="from9_139">139</td><td nowrap="nowrap">&nbsp;&nbsp;&nbsp;&nbsp;Resident&nbsp;Community&nbsp;Room,&nbsp;Bike&nbsp;Parking,&nbsp;Outdoor&nbsp;Terrace,&nbsp;On-site&nbsp;laundry,&nbsp;Street&nbsp;parking&nbsp;only.</td><td class="diff_next"></td><td class="diff_header" id="to9_153">153</td><td nowrap="nowrap">&nbsp;&nbsp;&nbsp;&nbsp;Resident&nbsp;Community&nbsp;Room,&nbsp;Bike&nbsp;Parking,&nbsp;Outdoor&nbsp;Terrace,&nbsp;On-site&nbsp;laundry,&nbsp;Street&nbsp;parking&nbsp;only.</td></tr>
        </tbody>
        <tbody>
            <tr><td class="diff_next" id="difflib_chg_to9__9"></td><td class="diff_header" id="from9_141">141</td><td nowrap="nowrap"></td><td class="diff_next"></td><td class="diff_header" id="to9_155">155</td><td nowrap="nowrap"></td></tr>
            <tr><td class="diff_next"></td><td class="diff_header" id="from9_142">142</td><td nowrap="nowrap">&nbsp;&nbsp;&nbsp;&nbsp;</td><td class="diff_next"></td><td class="diff_header" id="to9_156">156</td><td nowrap="nowrap">&nbsp;&nbsp;&nbsp;&nbsp;</td></tr>
            <tr><td class="diff_next"></td><td class="diff_header" id="from9_143">143</td><td nowrap="nowrap"></td><td class="diff_next"></td><td class="diff_header" id="to9_157">157</td><td nowrap="nowrap"></td></tr>
            <tr><td class="diff_next"><a href="#difflib_chg_to9__10">n</a></td><td class="diff_header" id="from9_144">144</td><td nowrap="nowrap">###&nbsp;&nbsp;**1&nbsp;BR**&nbsp;:&nbsp;<span class="diff_chg">1</span>&nbsp;unit,&nbsp;566&nbsp;square&nbsp;feet,&nbsp;3rd&nbsp;floor</td><td class="diff_next"><a href="#difflib_chg_to9__10">n</a></td><td class="diff_header" id="to9_158">158</td><td nowrap="nowrap">###&nbsp;&nbsp;**1&nbsp;BR**&nbsp;:&nbsp;<span class="diff_chg">2</span>&nbsp;unit<span class="diff_add">s</span>,<span class="diff_add">&nbsp;540&nbsp;-</span>&nbsp;566&nbsp;square&nbsp;feet,&nbsp;3rd&nbsp;floor</td></tr>
            <tr><td class="diff_next"></td><td class="diff_header" id="from9_145">145</td><td nowrap="nowrap"></td><td class="diff_next"></td><td class="diff_header" id="to9_159">159</td><td nowrap="nowrap"></td></tr>
            <tr><td class="diff_next"></td><td class="diff_header" id="from9_146">146</td><td nowrap="nowrap">###&nbsp;Additional&nbsp;Fees</td><td class="diff_next"></td><td class="diff_header" id="to9_160">160</td><td nowrap="nowrap">###&nbsp;Additional&nbsp;Fees</td></tr>
            <tr><td class="diff_next"></td><td class="diff_header" id="from9_147">147</td><td nowrap="nowrap"></td><td class="diff_next"></td><td class="diff_header" id="to9_161">161</td><td nowrap="nowrap"></td></tr>
        </tbody>
        <tbody>
            <tr><td class="diff_next" id="difflib_chg_to9__10"></td><td class="diff_header" id="from9_168">168</td><td nowrap="nowrap">1171&nbsp;Mesa&nbsp;Drive&nbsp;&nbsp;</td><td class="diff_next"></td><td class="diff_header" id="to9_182">182</td><td nowrap="nowrap">1171&nbsp;Mesa&nbsp;Drive&nbsp;&nbsp;</td></tr>
            <tr><td class="diff_next"></td><td class="diff_header" id="from9_169">169</td><td nowrap="nowrap">San&nbsp;Jose,&nbsp;CA&nbsp;95118</td><td class="diff_next"></td><td class="diff_header" id="to9_183">183</td><td nowrap="nowrap">San&nbsp;Jose,&nbsp;CA&nbsp;95118</td></tr>
            <tr><td class="diff_next"></td><td class="diff_header" id="from9_170">170</td><td nowrap="nowrap"></td><td class="diff_next"></td><td class="diff_header" id="to9_184">184</td><td nowrap="nowrap"></td></tr>
            <tr><td class="diff_next"><a href="#difflib_chg_to9__top">t</a></td><td class="diff_header"></td><td nowrap="nowrap"></td><td class="diff_next"><a href="#difflib_chg_to9__top">t</a></td><td class="diff_header" id="to9_185">185</td><td nowrap="nowrap"><span class="diff_add">&nbsp;&nbsp;*&nbsp;![Additional&nbsp;Information&nbsp;Envelope](https://housing.sanjoseca.gov/images/listing-legal.svg)</span></td></tr>
            <tr><td class="diff_next"></td><td class="diff_header"></td><td nowrap="nowrap"></td><td class="diff_next"></td><td class="diff_header" id="to9_186">186</td><td nowrap="nowrap"><span class="diff_add">&nbsp;</span></td></tr>
            <tr><td class="diff_next"></td><td class="diff_header"></td><td nowrap="nowrap"></td><td class="diff_next"></td><td class="diff_header" id="to9_187">187</td><td nowrap="nowrap"><span class="diff_add">##&nbsp;Additional&nbsp;Information</span></td></tr>
            <tr><td class="diff_next"></td><td class="diff_header"></td><td nowrap="nowrap"></td><td class="diff_next"></td><td class="diff_header" id="to9_188">188</td><td nowrap="nowrap"><span class="diff_add">&nbsp;</span></td></tr>
            <tr><td class="diff_next"></td><td class="diff_header"></td><td nowrap="nowrap"></td><td class="diff_next"></td><td class="diff_header" id="to9_189">189</td><td nowrap="nowrap"><span class="diff_add">Required&nbsp;documents&nbsp;and&nbsp;selection&nbsp;criteria</span></td></tr>
            <tr><td class="diff_next"></td><td class="diff_header"></td><td nowrap="nowrap"></td><td class="diff_next"></td><td class="diff_header" id="to9_190">190</td><td nowrap="nowrap"><span class="diff_add">&nbsp;</span></td></tr>
            <tr><td class="diff_next"></td><td class="diff_header"></td><td nowrap="nowrap"></td><td class="diff_next"></td><td class="diff_header" id="to9_191">191</td><td nowrap="nowrap"><span class="diff_add">###&nbsp;Required&nbsp;Documents</span></td></tr>
            <tr><td class="diff_next"></td><td class="diff_header"></td><td nowrap="nowrap"></td><td class="diff_next"></td><td class="diff_header" id="to9_192">192</td><td nowrap="nowrap"><span class="diff_add">&nbsp;</span></td></tr>
            <tr><td class="diff_next"></td><td class="diff_header"></td><td nowrap="nowrap"></td><td class="diff_next"></td><td class="diff_header" id="to9_193">193</td><td nowrap="nowrap"><span class="diff_add">Proof&nbsp;of&nbsp;income&nbsp;and&nbsp;assets&nbsp;will&nbsp;be&nbsp;required&nbsp;to&nbsp;determine&nbsp;eligibility.</span></td></tr>
            <tr><td class="diff_next"></td><td class="diff_header"></td><td nowrap="nowrap"></td><td class="diff_next"></td><td class="diff_header" id="to9_194">194</td><td nowrap="nowrap"><span class="diff_add">&nbsp;</span></td></tr>
            <tr><td class="diff_next"></td><td class="diff_header"></td><td nowrap="nowrap"></td><td class="diff_next"></td><td class="diff_header" id="to9_195">195</td><td nowrap="nowrap"><span class="diff_add">###&nbsp;Important&nbsp;Program&nbsp;Rules</span></td></tr>
            <tr><td class="diff_next"></td><td class="diff_header"></td><td nowrap="nowrap"></td><td class="diff_next"></td><td class="diff_header" id="to9_196">196</td><td nowrap="nowrap"><span class="diff_add">&nbsp;</span></td></tr>
            <tr><td class="diff_next"></td><td class="diff_header"></td><td nowrap="nowrap"></td><td class="diff_next"></td><td class="diff_header" id="to9_197">197</td><td nowrap="nowrap"><span class="diff_add">This&nbsp;property&nbsp;is&nbsp;regulated&nbsp;by&nbsp;TCAC.&nbsp;All&nbsp;TCAC&nbsp;Program&nbsp;rules&nbsp;and&nbsp;regulations</span></td></tr>
            <tr><td class="diff_next"></td><td class="diff_header"></td><td nowrap="nowrap"></td><td class="diff_next"></td><td class="diff_header" id="to9_198">198</td><td nowrap="nowrap"><span class="diff_add">apply.</span></td></tr>
            <tr><td class="diff_next"></td><td class="diff_header"></td><td nowrap="nowrap"></td><td class="diff_next"></td><td class="diff_header" id="to9_199">199</td><td nowrap="nowrap"><span class="diff_add">&nbsp;</span></td></tr>
        </tbody>
    </table>
<hr>
</body>
</html>
"""

# https://stackoverflow.com/questions/312443/how-do-i-split-a-list-into-equally-sized-chunks
def chunkify(lst, n):
  """Yield n-sized chunks from the list 'lst'."""
  for i in range(0, len(lst), n):
      yield lst[i:i + n]


class ErrorOnEmptyData(filters.FilterBase):
  __kind__ = 'if_empty'

  __supported_subfilters__ = {
    'action': 'What to do if the input data is empty [error, warn]',
  }

  __default_subfilter__ = 'action'

  def filter(self, data, subfilter):
    if subfilter['action'] not in ['error', 'warn']:
      raise ValueError('Invalid value for "action", must be "error" or "warn"')
    msg = 'Filter input is empty, no text to process.'
    if data.strip() == "":
      if subfilter['action'] == 'error':
        raise ValueError(msg)
      elif subfilter['action'] == 'warn':
        logger.warn(msg)
    return data


class SelectiveFilter(filters.FilterBase):
  __kind__ = 'selective'

  __supported_subfilters__ = {
    'filter': 'Name of the filter to be selectively applied',
    'select_pattern': 'List of patterns defining the selection',
    'invert_selection': 'Invert the selection made with select_pattern',
    '<any>': 'Subfilters associated with "filter"',
  }

  def filter(self, data, subfilter):
    if 'select_pattern' not in subfilter:
      raise ValueError('{} needs a select_pattern'.format(self.__kind__))
    subfilter['invert_selection'] = subfilter.get('invert_selection', False)
    select_pattern = subfilter['select_pattern']
    if not isinstance(select_pattern, list):
      select_pattern = [select_pattern]
    matched = any(re.match(p, self.job.get_location()) for p in select_pattern)
    do_process = not matched if subfilter['invert_selection'] else matched
    target_filter_kind = subfilter['filter']
    target_subfilter = dict(subfilter)
    for key in self.__supported_subfilters__:
      if key != '<any>':
        target_subfilter.pop(key)
    if not do_process:
      logger.info('Selectively skipping application of filter %r, subfilter %r to %s', target_filter_kind, target_subfilter, self.job.get_location())
      return data
    return filters.FilterBase.process(target_filter_kind, target_subfilter, self.state, data)


class RealPageBase(filters.FilterBase):
  def filter(self, data, subfilter):
    filtered = filters.FilterBase.process('jq', {'query': self.__query__}, self.state, data)
    filtered = filters.FilterBase.process('remove-duplicate-lines', {}, self.state, filtered)
    filtered = filters.FilterBase.process('sort', {}, self.state, filtered)
    filtered = filters.FilterBase.process('re.sub', {'pattern': '"'}, self.state, filtered)
    filtered = filters.FilterBase.process('re.sub', {'pattern': r'\\n', 'repl': r'\n'}, self.state, filtered)
    return filtered


class RealPageUnits(RealPageBase):
  """Filter for pretty-printing units JSON data from the realpage API."""

  __kind__ = 'realpage_units'
  __query__ = r'.response // . | .units[]? | "\(.numberOfBeds) BR\n---\n$\(.rent)/month\n\(.leaseStatus)\n\n"'


class RealPageFloorplans(RealPageBase):
  """Filter for pretty-printing floorplan JSON data from the realpage API."""

  __kind__ = 'realpage_floorplans'
  __query__ = r'.response // . | .floorplans[]? | "\(.name)\n---\n\(.bedRooms) BR\n\(.rentType)\n\(.rentRange)\n\n"'


class RegexSuperSub(filters.FilterBase):
  """Replace text with regex; can match within a line or substring."""

  __kind__ = 're.ssub'

  __supported_subfilters__ = {
    'substring': 'Regular expression for a substring to find "pattern" within',
    'pattern': 'Regular expression to search for (required)',
    'repl': 'Replacement string (default: empty string)',
  }

  __default_subfilter__ = 'pattern'

  def filter(self, data, subfilter):
    def replaceWithin(match):
      return re.sub(subfilter['pattern'], subfilter.get('repl', ''), match[0])
    if 'pattern' not in subfilter:
      raise ValueError('{} needs a pattern'.format(self.__kind__))
    # Default: Replace with empty string if no "repl" value is set
    if 'substring' in subfilter:
      return re.sub(subfilter['substring'], replaceWithin, data)
    else:
      return re.sub(subfilter['pattern'], subfilter.get('repl', ''), data)


class GcsFileReporter(reporters.HtmlReporter):
  """Custom reporter that writes an HTML file to Google Cloud Storage."""

  __kind__ = 'gcs'

  def submit(self):
    filename_args = {
      'datetime': self.report.start.strftime('%Y-%m-%d-%H%M%S'),
    }
    filename = self.config['filename'].format(**filename_args)
    local_path = os.path.join(os.path.expanduser(self.config['local_dir']), filename)
    # TODO: make necessary parent directories
    with open(local_path, 'w') as file:
      for part in super().submit():
        file.write('%s\n' % part)
    logger.debug('Wrote %s', local_path)
    cmd = ['gsutil', 'cp', local_path, 'gs://%s' % (os.path.join(self.config['bucket'], self.config['gcs_dir']))]
    logger.debug('Calling %s', ' '.join(cmd))
    result = subprocess.run(cmd)
    if result.returncode == 0:
      logger.info('Upload successful, removing %s', local_path)
      os.remove(local_path)
    else:
      logger.error('Could not upload to Google Cloud Store.  The local file (%s) has not been removed.', local_path)


class CustomTextEmailReporter(reporters.TextReporter):
  """Custom reporter that sends a text email"""

  __kind__ = 'custom_email'

  def submit(self):
    filtered_job_states = list(self.report.get_filtered_job_states(self.job_states))

    subject_args = {
      'count': len(filtered_job_states),
      'jobs': ', '.join(job_state.job.pretty_name() for job_state in filtered_job_states),
      'datetime': self.report.start.strftime('%b %d, %Y %I:%M:%S %p'),
    }
    subject = self.config['subject'].format(**subject_args)
    logger.debug(subject)
    body_text = '\n'.join(super().submit())

    if not body_text:
      logger.debug('Not sending e-mail (no changes)')
      return
    details_url_args = {
      'datetime': self.report.start.strftime('%Y-%m-%d-%H%M%S'),
    }
    details_url = self.config['details_url'].format(**details_url_args)
    body_text = """
The following websites have changed.

For details, visit %s

%s
""" % (details_url, body_text)

    if self.config['method'] == "smtp":
      smtp_user = self.config['smtp'].get('user', None) or self.config['from']
      # Legacy support: The current smtp "auth" setting was previously called "keyring"
      if 'keyring' in self.config['smtp']:
        logger.info('The SMTP config key "keyring" is now called "auth". See https://urlwatch.readthedocs.io/en/latest/deprecated.html')
      use_auth = self.config['smtp'].get('auth', self.config['smtp'].get('keyring', False))
      mailer = SMTPMailer(smtp_user, self.config['smtp']['host'], self.config['smtp']['port'],
                self.config['smtp']['starttls'], use_auth,
                self.config['smtp'].get('insecure_password'))
    elif self.config['method'] == "sendmail":
      mailer = SendmailMailer(self.config['sendmail']['path'])
    else:
      logger.error('Invalid entry for method {method}'.format(method=self.config['method']))

    reply_to = self.config.get('reply_to', self.config['from'])
    if self.config['html']:
      body_html = '\n'.join(self.convert(reporters.HtmlReporter).submit())

      msg = mailer.msg_html(self.config['from'], self.config['to'], reply_to, subject, body_text, body_html)
    else:
      msg = mailer.msg_plain(self.config['from'], self.config['to'], reply_to, subject, body_text)

    mailer.send(msg)


class JiraReporter(reporters.ReporterBase):

  __kind__ = 'jira'

  # https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issues/#api-rest-api-3-issue-bulk-post
  _MAX_BATCH_SIZE = 50

  def submit(self):
    issues = []
    local_time = time.localtime()
    for job_state in self.report.get_filtered_job_states(self.job_states):
      if job_state.verb not in ['error', 'changed']:
        continue
      issue = {
        'fields': {
          'project': {'id': self.config['project']},
          'issuetype': {'id': self.config['issuetype']},
        },
      }
      pretty_name = job_state.job.pretty_name()
      url = job_state.job.get_location()
      summary_parts = [f'{job_state.verb.capitalize()}:', pretty_name]
      if url:
        issue['fields'][self.config['url_field']] = url
        if url != pretty_name:
          summary_parts.append(f'({url})')
      summary = ' '.join(summary_parts)
      issue['fields']['summary'] = summary
      description = self._adf_doc()
      description['content'].append(self._adf_header('https://example.com'))
      if job_state.verb == 'error':
          description['content'].append(self._adf_text(job_state.traceback.strip()))
      elif job_state.verb == 'changed':
          description['content'].append(self._adf_diff(job_state.get_diff()))
      issue['fields']['description'] = description
      issue['fields'][self.config['reported_field']] = time.strftime(
        '%Y-%m-%d', local_time)
      print(json.dumps(issue, indent=2))
      issues.append(issue)
    # print(issues)
    self._create_issues(issues)


  def _create_issues(self, issues):
    # Make sure there's an entry in .netrc matching the host (or default).
    try:
      netrc_obj = netrc.netrc()
    except FileNotFoundError as e:
      logging.error(f'The {self.__kind__} reporter requires API '
        'credentials to be stored in a .netrc file, and that file does not '
        'seem to exist.')
      raise
    netloc = urllib.parse.urlparse(self.config['site_url']).netloc
    if not netrc_obj.authenticators(netloc):
      raise RuntimeError(f'{netloc} was not found in your '
        '.netrc file and no default credentials exist in that file.\nAdd Jira '
        'API credentials to your .netrc file to use this reporter.')
    for chunk in chunkify(issues, self._MAX_BATCH_SIZE):
      # Note auth is set by a local .netrc file with an entry for
      # the value of self.config['site_url']
      response = requests.post(
        urllib.parse.urljoin(self.config['site_url'], 'rest/api/3/issue/bulk'),
        headers={
          "Accept": "application/json",
          "Content-Type": "application/json"
         },
        json={'issueUpdates': chunk},
      )
      print(response.status_code)
      print(response.text)
      response.raise_for_status()

  def _adf_doc(self):
    return {
      'type': 'doc',
      'version': 1,
      'content': []
    }

  def _adf_header(self, url):
    return {
      'type': 'paragraph',
      'content': [
        {
          'type': 'text',
          'text': 'Link to the original change report',
          'marks': [
            {
              'type': 'link',
              'attrs': {
                'href': url
              }
            }
          ]
        }
      ]
    }

  def _adf_diff(self, diff):
    adf = {
      'type': 'paragraph',
      'content': [
        {
          'text': text,
          'type': 'text',
        }
      ]
    }
    for line in diff:
      if line.startswith('+'):
        adf['content'].append({
          'text': line,
          'type': 'text',
          'marks': [
            {'type': 'strong'},
            {'type': 'textColor', 'attrs': {'color': '#1f883d'}},
          ],
        })
      elif line.startswith('-'):
        adf['content'].append({
          'text': line,
          'type': 'text',
          'marks': [
            {'type': 'strong'},
            {'type': 'textColor', 'attrs': {'color': '#cf222e'}},
          ],
        })
      else:
        if 'marks' in adf['content'][-1]:
          # Last content node is a colored one.  Create a new one for the plain
          # text.
          adf['content'].append({
            'text': line,
            'type': 'text',
          })
        else:
          # Last content node is plain text.  Just append this line onto that
          # text node.
          adf['content'][-1]['text'] += line

  def _adf_text(self, text):
    return {
      'type': 'paragraph',
      'content': [
        {
          'text': text,
          'type': 'text'
        }
      ]
    }


class JiraReporterOld(reporters.HtmlReporter):

  __kind__ = 'jira-old'

  # https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issues/#api-rest-api-3-issue-bulk-post
  _MAX_BATCH_SIZE = 50

  def submit(self):
    html_report = '\n'.join(super().submit())
    self._submit_from_html(TEST_HTML)
    # self._submit_from_html(html_report)

  def _create_issues(self, issues):
    # Make sure there's an entry in .netrc matching the host (or default).
    try:
      netrc_obj = netrc.netrc()
    except FileNotFoundError as e:
      logging.error(f'The {self.__kind__} reporter requires API '
        'credentials to be stored in a .netrc file, and that file does not '
        'seem to exist.')
      raise
    netloc = urllib.parse.urlparse(self.config['site_url']).netloc
    if not netrc_obj.authenticators(netloc):
      raise RuntimeError(f'{netloc} was not found in your '
        '.netrc file and no default credentials exist in that file.\nAdd Jira '
        'API credentials to your .netrc file to use this reporter.')
    for chunk in chunkify(issues, self._MAX_BATCH_SIZE):
      # Note auth is set by a local .netrc file with an entry for
      # the value of self.config['site_url']
      response = requests.post(
        urllib.parse.urljoin(self.config['site_url'], 'rest/api/3/issue/bulk'),
        headers={
          "Accept": "application/json",
          "Content-Type": "application/json"
         },
        json={'issueUpdates': chunk},
      )
      print(response.status_code)
      print(response.text)
      response.raise_for_status()

  def _submit_from_html(self, html):
    soup = BeautifulSoup(html, 'lxml')
    issues = []
    local_time = time.localtime()
    for heading in soup.find_all('h2'):
      verb = heading.find('span', class_='verb')
      if verb.string not in ['error:', 'changed:']:
        continue
      issue = {
        'fields': {
          'project': {'id': self.config['project']},
          'issuetype': {'id': self.config['issuetype']},
        },
      }
      title = verb.next_sibling.next_sibling
      url = title['href']
      summary_parts = [str(verb.string.capitalize()), str(title.string)]
      if url:
        issue['fields'][self.config['url_field']] = url
        if url != title.string:
          summary_parts.append(f'({url})')
      summary = ' '.join(summary_parts)
      issue['fields']['summary'] = summary
      content = heading.next_sibling.next_sibling
      description = self._adf_doc()
      description['content'].append(self._adf_header('https://example.com'))
      if content.name == 'table':
        description['content'].append(self._adf_table(content))
      else:
        description['content'].append(self._adf_text(content))
      issue['fields']['description'] = description
      issue['fields'][self.config['reported_field']] = time.strftime(
        '%Y-%m-%d', local_time)
      print(json.dumps(issue, indent=2))
      issues.append(issue)
    # print(issues)
    self._create_issues(issues)

  def _adf_doc(self):
    return {
      'type': 'doc',
      'version': 1,
      'content': []
    }

  def _adf_header(self, url):
    return {
      'type': 'paragraph',
      'content': [
        {
          'type': 'text',
          'text': 'Link to the original change report',
          'marks': [
            {
              'type': 'link',
              'attrs': {
                'href': url
              }
            }
          ]
        }
      ]
    }

  def _adf_table(self, table):
    adf = {
      'type': 'table',
      'attrs': {
        'isNumberColumnEnabled': False,
        'layout': 'default',
      },
      'content': []
    }
    for elem in table.children:
      if elem.name == 'thead':
        adf['content'].extend(self._adf_thead(elem))
      elif elem.name == 'tbody':
        adf['content'].extend(self._adf_tbody(elem))
    return adf

  def _adf_thead(self, thead):
    adf = []
    for elem in thead.children:
      if elem.name == 'tr':
        adf.append(self._adf_tr(elem))
    return adf

  def _adf_tbody(self, thead):
    adf = []
    for elem in thead.children:
      if elem.name == 'tr':
        adf.append(self._adf_tr(elem))
    return adf

  def _adf_tr(self, tr):
    adf = {
      'type': 'tableRow',
      'content': [],
    }
    for elem in tr.children:
      if elem.name == 'td':
        if 'diff_next' in elem.get('class', []):
          continue
        adf['content'].append(self._adf_td(elem))
      elif elem.name == 'th':
        if 'diff_next' in elem.get('class', []):
          continue
        adf['content'].append(self._adf_th(elem))
    return adf

  def _adf_td(self, td):
    adf = {
      'type': 'tableCell',
      'content': [
        {
          'type': 'paragraph',
          'content': []
        }
      ]
    }
    for elem in td.children:
      adf['content'][0]['content'].append(self._adf_content(elem))
    return adf

  def _adf_th(self, th):
    adf = {
      'type': 'tableHeader',
      'attrs': {
        'colspan': 2,
        'colwidth': [48, 373]
      },
      'content': [
        {
          'type': 'paragraph',
          'content': []
        }
      ]
    }
    for elem in th.children:
      adf['content'][0]['content'].append(self._adf_content(elem, marks=[{'type': 'strong'}]))
    return adf

  def _adf_content(self, elem, marks=[]):
    adf = {
      'type': 'text',
      'text': '' if elem.string is None else str(elem.string),
      'marks': []
    }
    if elem.name == 'span':
      if 'diff_add' in elem.get('class', []):
        adf['marks'].extend([
          {
            'type': 'strong'
          },
          {
            'type': 'textColor',
            'attrs': {
              'color': '#1f883d'
            }
          }
        ])
      if 'diff_sub' in elem.get('class', []):
        adf['marks'].extend([
          {
            'type': 'strong'
          },
          {
            'type': 'textColor',
            'attrs': {
              'color': '#cf222e'
            }
          }
        ])
      if 'diff_chg' in elem.get('class', []):
        adf['marks'].extend([
          {
            'type': 'strong'
          },
          {
            'type': 'textColor',
            'attrs': {
              'color': '#ffab00'
            }
          }
        ])
    adf['marks'].extend(marks)
    return adf


  # def _xformat_table(self, tag):
  #   headers = tag.find_all('th', class_='diff_header')
  #   adf_headers = []
  #   for header in headers:
  #     adf_headers.extend([
  #       {
  #         'type': 'tableHeader',
  #         'attrs': {
  #           'colwidth': [48]
  #         },
  #         'content': [
  #           {
  #             'type': 'paragraph',
  #             'content': []
  #           }
  #         ]
  #       },
  #       {
  #         'type': 'tableHeader',
  #         'attrs': {
  #           'colwidth': [373]
  #         },
  #         'content': [
  #           {
  #             'type': 'paragraph',
  #             'content': [
  #               {
  #                 'type': 'text',
  #                 'text': '' if header.string is None else str(header.string),
  #                 'marks': [
  #                   {
  #                     'type': 'strong'
  #                   }
  #                 ]
  #               }
  #             ]
  #           }
  #         ]
  #       }
  #     ])
  #   rows = tag.find_all('tr')
  #   adf_rows = [
  #     {
  #       'type': 'tableRow',
  #       'content': adf_headers,
  #     },
  #   ]
  #   for row in rows:
  #     cells = row.find_all('td')
  #     adf_cells = []
  #     for cell in cells:
  #       if 'diff_next' in cell.get('class', []):
  #         continue
  #       adf_cell = {
  #         'type': 'tableCell',
  #         'content': [
  #           {
  #             'type': 'paragraph',
  #             'content': [
  #               {
  #                 'type': 'text',
  #                 'text': '' if cell.string is None else str(cell.string),
  #               }
  #             ]
  #           }
  #         ]
  #       }
  #       if len(cell.contents) > 0 and cell.contents[0].name is not None:
  #         cell_class = cell.contents[0].get('class', [])
  #         if 'diff_sub' in cell_class:
  #           adf_cell['content'][0]['content'][0]['marks'] = [
  #             {
  #               'type': 'strong'
  #             },
  #             {
  #               'type': 'textColor',
  #               'attrs': {
  #                 'color': '#cf222e'
  #               }
  #             }
  #           ]
  #         elif 'diff_add' in cell_class:
  #           adf_cell['content'][0]['content'][0]['marks'] = [
  #             {
  #               'type': 'strong'
  #             },
  #             {
  #               'type': 'textColor',
  #               'attrs': {
  #                 'color': '#1f883d'
  #               }
  #             }
  #           ]
  #       adf_cells.append(adf_cell)
  #     if not adf_cells:
  #       continue
  #     adf_rows.append({
  #       'type': 'tableRow',
  #       'content': adf_cells,
  #     })

  #   ret = {
  #     'type': 'doc',
  #     'version': 1,
  #     'content': [
  #       {
  #         'type': 'paragraph',
  #         'content': [
  #           {
  #             'type': 'text',
  #             'text': 'Link to the original change report',
  #             'marks': [
  #               {
  #                 'type': 'link',
  #                 'attrs': {
  #                   'href': 'https://example.com'
  #                 }
  #               }
  #             ]
  #           }
  #         ]
  #       },
  #       {
  #         'type': 'table',
  #         'attrs': {
  #           'isNumberColumnEnabled': False,
  #           'layout': 'default',
  #         },
  #         'content': adf_rows,
  #       },
  #     ]
  #   }
  #   print(json.dumps(ret, indent=2))
  #   return ret

  def _adf_text(self, tag):
    return {
      'type': 'paragraph',
      'content': [
        {
          'text': '' if tag.string is None else str(tag.string),
          'type': 'text'
        }
      ]
    }
