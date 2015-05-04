RLTail (Rotated Log Tail)
====

This bash script tails logs that have a variable part. When the variable part changes, it stops
tailing the current file(s) and starts tailing the new one(s).

It supports date variable part and numeric incremental part.

```
Use: rltail.sh [--dateformat <dateformat>] [--pattern <pattern>] [--number <number>] <fixpart> [<fixpart> ..]

 --dateformat <dateformat>    : For log files that its filename changing part is a date, specify the format as
                                'man date' FORMAT section. Default "%Y%m%d%H" (if no <number> specified)
 --number <number>            : If the filename changing part is just a incremental number. It can take the form of:
                                  1: It will generate 1,2,3,4,...
                                  01: It will generate 01,02,03,04...
                                  001: 001,002,003,004...
                                  And so on.
                                Default: Not defined.
 --pattern <pattern>          : Pattern of filename. Two special variables exist:
                                  %F: <fixpart>
                                  %D: <dateformat>
                                  %N: <number>
                                Default "%F-%D.log".
 <fixpart>                    : The part of the filename that does not change.

 NOTE: dateformat and number are mutually exclusive

Examples:
  rltail.sh access
    Will tail access-2015043017.log, access-2015043018.log, ...
  rltail.sh --number 01 --pattern "%F-%N.log" postfix
    Will tail postfix-01.log, postfix-02.log, ...
  rltail.sh --number 05 --pattern "%F-%N.log" access error
    Will tail access-05.log and error-05.log, then access-06.log and error-06.log, ...
```

