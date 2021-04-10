import unittest 
from unittest.mock import patch

@patch('praw.Reddit.__init__')