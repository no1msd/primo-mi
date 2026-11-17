; PRIMO MI - a BASIC helper for the Microkey PRIMO A-64.
;
; You type a question in Hungarian; a small neural network reads it and chooses
; one of the answers of train/kb.py; the answer is printed.  The network does
; not write the answers.  Numbers in the question (a line number, how far to
; count, a sum) are put into the answer by fixed rules, not by the network.
;
;   line      the ROM's own line editor
;   symbols   lower case, accents folded away, every digit the same symbol
;   groups    all runs of 1..4 symbols; each is hashed to one of NB rows
;   hidden    S[d] = (rows with +1 in d) - (rows with -1 in d);  u[d] = TANH[S[d]]
;   scores    Z[j] = sum over d of (L[j][d]*u[d] + 32) >> 6  +  bias[j]
;   answer    the j with the largest Z[j]; if the next best is less than UNSURE
;             below it, "I am not sure I understand" is printed first
;
; train/helper.py describes the network, train/ref_helper.py repeats this file in
; Python on the same bytes and must agree with it.  No interrupts are switched
; off and no ROM state is changed, except the pointer to the extra glyphs.
;
; Assemble:  z88dk-z80asm -b -m -Imi -obuild/asm/mi.bin z80/mi.asm

    org     $4400

    INCLUDE "model.inc"         ; NB rows, ND hidden units, NC answers, UNSURE, NONE

    defc    ROM_PUTC = $0015    ; print the character in A; needs IX as BASIC left it
    defc    ROM_LINE = $0361    ; read a line; HL = one before the text, carry = BRK
    defc    USERFONT = $404B    ; pointer to the glyphs of characters $80..
    defc    COLUMNS  = 42       ; the ROM prints 6 pixel wide characters
    defc    MAXLINE  = 60       ; characters of the line that are read

  IF NB != 1024
    ERROR "the bucket arithmetic below is written for 1024 rows"
  ENDIF
  IF ND != 64
    ERROR "the row arithmetic below is written for 64 hidden units"
  ENDIF

; ---- memory that is not part of the tape image ------------------------------
    defc    WORK   = $E000      ; the tape image must end below this
    defc    PLUS   = WORK       ; ND counters: rows with +1
    defc    MINUS  = WORK + ND  ; ND counters: rows with -1 (must follow PLUS)
    defc    UVEC   = WORK + $80 ; ND hidden activations
    defc    PT     = WORK + $100        ; 16 products of the current hidden unit
    defc    ZACC   = WORK + $200        ; NC scores, 2 bytes each
    defc    LINE   = WORK + $400        ; the typed line, 0 at its end
    defc    SYMS   = WORK + $500        ; its symbols

; =============================================================================
start:
    ld      (exit_sp+1),sp
    ld      hl,(USERFONT)
    ld      (exit_font+1),hl
    ld      hl,font
    ld      (USERFONT),hl
    ld      a,12                ; clear the screen
    call    ROM_PUTC
    ld      hl,title
    call    puts
    call    pc_flush

ask:
    ld      a,'>'
    call    ROM_PUTC
    ld      a,' '
    call    ROM_PUTC
    call    ROM_LINE
    jr      c,exit              ; BRK: back to BASIC
    inc     hl
    call    take_line
    jr      c,ask               ; nothing typed
got_line:
    call    features
    call    hidden
    call    scores
chosen:                         ; A = the answer
    push    af
    call    find_number
    call    find_sum
    xor     a
    ld      (column),a
    pop     af
    cp      NONE                ; "I do not know that" is never hedged
    jr      z,sure
    push    af
    ld      a,(unsure)
    or      a
    ld      hl,hedge
    call    nz,puts
    pop     af
sure:
    call    print_answer
    call    pc_flush_nl
    ld      a,13                ; an empty line
    call    ROM_PUTC
    jp      ask

exit:
exit_font:
    ld      hl,0
    ld      (USERFONT),hl
exit_sp:
    ld      sp,0
    ret

; ---- the typed line and its symbols -------------------------------------------
; HL -> the text, 0 at its end.  Carry on return: there is nothing in it.
take_line:
    ld      de,LINE
    ld      b,MAXLINE
tl_copy:
    ld      a,(hl)
    or      a
    jr      z,tl_end
    ld      (de),a
    inc     hl
    inc     de
    djnz    tl_copy
tl_end:
    xor     a
    ld      (de),a
    ld      hl,LINE
    ld      de,SYMS
    ld      a,1                 ; a space in front
    ld      (de),a
    inc     de
    ld      c,a                 ; C = the last symbol
tl_sym:
    ld      a,(hl)
    inc     hl
    or      a
    jr      z,tl_done
    cp      $80
    jr      nc,tl_sym
    push    hl
    ld      hl,charmap
    add     a,l
    ld      l,a
    jr      nc,ASMPC+3
    inc     h
    ld      a,(hl)
    pop     hl
    or      a
    jr      z,tl_sym            ; a character that means nothing
    cp      1
    jr      nz,tl_put
    cp      c
    jr      z,tl_sym            ; a second space
tl_put:
    ld      (de),a
    inc     de
    ld      c,a
    jr      tl_sym
tl_done:
    ld      a,c
    cp      1
    jr      z,tl_len
    ld      a,1                 ; a space behind
    ld      (de),a
    inc     de
tl_len:
    ld      a,e                 ; SYMS is at the start of a page
    ld      (nsym),a
    cp      2
    ret

; ---- hidden sums: add the row of every character group -------------------------
features:
    ld      hl,PLUS
    ld      de,PLUS+1
    ld      bc,2*ND-1
    ld      (hl),0
    ldir
    ld      a,1
ft_n:
    ld      (ngram),a
    ld      b,a
    ld      a,(nsym)
    sub     b
    ret     c                   ; fewer symbols than the group is long
    inc     a
    ld      (count),a           ; groups of this length
    ld      a,b                 ; seed = n * $2F31
    ld      hl,0
    ld      de,$2F31
ft_seed:
    add     hl,de
    djnz    ft_seed
    ld      (seed),hl
    ld      hl,SYMS
    ld      (fpos),hl
ft_i:
    ld      hl,(seed)
    ld      de,(fpos)
    ld      a,(ngram)
    ld      b,a
ft_h:                           ; h = h*33 xor symbol
    push    bc
    ld      b,h
    ld      c,l
    add     hl,hl
    add     hl,hl
    add     hl,hl
    add     hl,hl
    add     hl,hl
    add     hl,bc
    ld      a,(de)
    inc     de
    xor     l
    ld      l,a
    pop     bc
    djnz    ft_h
    ld      a,l                 ; row = (h xor (h >> 7)) and 1023
    rlca
    and     1
    ld      c,a
    ld      a,h
    add     a,a
    or      c
    xor     l
    ld      e,a
    ld      a,h
    rlca
    and     1
    xor     h
    and     3
    ld      d,a
    ex      de,hl
    add     hl,hl               ; 16 bytes per row
    add     hl,hl
    add     hl,hl
    add     hl,hl
    ld      de,table
    add     hl,de
    ex      de,hl
    ld      hl,PLUS             ; 64 bits "+1", then 64 bits "-1"
    ld      b,2*ND/8
ft_byte:
    ld      a,(de)
    inc     de
  REPT 8
    add     a,a
    jr      nc,ASMPC+3
    inc     (hl)
    inc     l
  ENDR
    djnz    ft_byte
    ld      hl,(fpos)
    inc     hl
    ld      (fpos),hl
    ld      hl,count
    dec     (hl)
    jp      nz,ft_i
    ld      a,(ngram)
    inc     a
    cp      5
    jp      nz,ft_n
    ret

; ---- hidden activations: u = TANH[clamp(plus - minus)] ---------------------------
hidden:
    ld      hl,PLUS
    ld      de,UVEC
    ld      b,ND
hd_loop:
    ld      a,(hl)
    set     6,l                 ; MINUS = PLUS + 64
    sub     (hl)
    res     6,l
    jr      c,hd_neg
    cp      128
    jr      c,hd_ok
    ld      a,127
    jr      hd_ok
hd_neg:
    cp      128
    jr      nc,hd_ok
    ld      a,128               ; -128
hd_ok:
    xor     $80                 ; table index = sum + 128
    push    bc
    ld      c,a
    ld      b,tanh/256
    ld      a,(bc)
    pop     bc
    ld      (de),a
    inc     de
    inc     l
    djnz    hd_loop
    ret

; ---- scores, and the largest of them ---------------------------------------------
scores:
    ld      hl,bias
    ld      de,ZACC
    ld      bc,NC*2
    ldir
    ld      hl,ocodes
    ld      (cptr),hl
    ld      hl,UVEC
    ld      b,ND
sc_dim:
    push    bc
    push    hl
    ld      a,(hl)
    call    make_pt
    ld      hl,(cptr)
    ld      b,PT/256
    ld      d,NC/2
    exx
    ld      hl,ZACC
    exx
sc_pair:                        ; one byte = the codes of two answers
    ld      a,(hl)
    and     15
    ld      c,a
    ld      a,(bc)
    exx
    add     a,(hl)
    ld      (hl),a
    inc     hl
    jr      nc,ASMPC+3
    inc     (hl)
    inc     hl
    exx
    ld      a,(hl)
    rrca
    rrca
    rrca
    rrca
    and     15
    ld      c,a
    ld      a,(bc)
    exx
    add     a,(hl)
    ld      (hl),a
    inc     hl
    jr      nc,ASMPC+3
    inc     (hl)
    inc     hl
    exx
    inc     hl
    dec     d
    jr      nz,sc_pair
    ld      (cptr),hl
    pop     hl
    inc     hl
    pop     bc
    djnz    sc_dim

    ld      hl,ZACC             ; the first of the largest scores
    ld      e,(hl)
    inc     hl
    ld      d,(hl)
    inc     hl
    xor     a
    ld      (best),a
    push    hl
    ld      hl,-8192            ; below every score
    ld      (second),hl
    pop     hl
    ld      bc,(NC-1)*256+1     ; B = how many are left, C = the next one's number
am_loop:
    push    bc
    ld      c,(hl)
    inc     hl
    ld      b,(hl)
    inc     hl
    push    hl
    ld      h,b
    ld      l,c
    or      a
    sbc     hl,de               ; scores are small: the sign of the difference is right
    jr      z,am_second
    jp      m,am_second
    ld      (second),de         ; a new best; the old one is the second
    ld      d,b
    ld      e,c
    pop     hl
    pop     bc
    ld      a,c
    ld      (best),a
    jr      am_next
am_second:
    ld      hl,(second)
    or      a
    sbc     hl,bc
    jp      p,am_keep
    ld      (second),bc
am_keep:
    pop     hl
    pop     bc
am_next:
    inc     c
    djnz    am_loop
    ld      hl,(second)
    ex      de,hl
    or      a
    sbc     hl,de               ; best - second
    ld      de,UNSURE
    or      a
    sbc     hl,de               ; carry: closer than UNSURE
    ld      a,0
    rla
    ld      (unsure),a
    ld      a,(best)
    ret

; PT[code] = ((level * v + 32) >> 6) + 64 for the 16 levels; A = v.
; The levels are symmetric: dlevels holds the steps between the positive ones.
make_pt:
    ld      e,a
    add     a,a
    sbc     a,a
    ld      d,a                 ; DE = v
    ld      hl,0
    ld      bc,dlevels
    exx
    ld      hl,PT+8
    ld      de,PT+7
    ld      b,8
    exx
mp_level:
    ld      a,(bc)
    inc     bc
mp_add:
    add     hl,de
    dec     a
    jr      nz,mp_add           ; HL = level * v
    push    hl
    call    mp_round
    exx
    ld      (hl),a
    inc     hl
    exx
    pop     hl
    push    hl
    xor     a                   ; HL = -HL
    sub     l
    ld      l,a
    sbc     a,a
    sub     h
    ld      h,a
    call    mp_round
    exx
    ld      (de),a
    dec     de
    dec     b
    exx
    pop     hl
    jr      nz,mp_level
    ret
mp_round:                       ; A = ((HL + 32) >> 6) + 64
    ld      a,l
    add     a,32
    ld      l,a
    jr      nc,ASMPC+3
    inc     h
    add     hl,hl
    add     hl,hl
    ld      a,h
    add     a,64
    ret

; ---- numbers in the line ---------------------------------------------------------
; The largest number of up to four digits; digits stuck to a letter or a slash
; ("L3 Error", "/0 Error") do not count.  numlen = 0: none.
find_number:
    xor     a
    ld      (numlen),a
    ld      hl,LINE
    ld      c,' '               ; the character before
fn_next:
    ld      a,(hl)
    or      a
    ret     z
    call    isdigit
    jr      c,fn_run
    ld      c,a
    inc     hl
    jr      fn_next
fn_run:
    ld      d,h
    ld      e,l                 ; DE = its first digit
    ld      b,0                 ; B = its length
fn_count:
    ld      a,(hl)
    call    isdigit
    jr      nc,fn_end
    inc     hl
    inc     b
    jr      fn_count
fn_end:
    push    hl
    ld      a,c
    cp      '/'
    jr      z,fn_skip
    call    isletter
    jr      c,fn_skip
    ld      a,b
    cp      5
    jr      nc,fn_skip
fn_zero:                        ; leading zeros off
    ld      a,b
    dec     a
    jr      z,fn_cmp
    ld      a,(de)
    cp      '0'
    jr      nz,fn_cmp
    inc     de
    dec     b
    jr      fn_zero
fn_cmp:
    ld      a,(numlen)
    cp      b
    jr      c,fn_take           ; longer than the best so far
    jr      nz,fn_skip          ; shorter
    push    de
    push    bc
    ld      hl,(numptr)
fn_lex:
    ld      a,(de)
    cp      (hl)
    jr      nz,fn_differ
    inc     de
    inc     hl
    djnz    fn_lex
fn_differ:                      ; carry: smaller; zero: the same
    pop     bc
    pop     de
    jr      c,fn_skip
    jr      z,fn_skip
fn_take:
    ld      (numptr),de
    ld      a,b
    ld      (numlen),a
fn_skip:
    pop     hl
    ld      c,'0'
    jr      fn_next

; The first sum: number, then one or more times an operator and a number, with
; spaces allowed around the operators.  sumptr = 0: none.
find_sum:
    ld      hl,0
    ld      (sumptr),hl
    ld      hl,LINE
fs_try:
    ld      a,(hl)
    or      a
    ret     z
    call    isdigit
    jr      c,fs_at
    inc     hl
    jr      fs_try
fs_at:
    push    hl
    call    parse_num
    ld      b,0                 ; B = operators so far
fs_group:
    ld      d,h
    ld      e,l                 ; DE = end of what matches so far
fs_sp1:
    ld      a,(hl)
    cp      ' '
    jr      nz,fs_op
    inc     hl
    jr      fs_sp1
fs_op:
    cp      '+'
    jr      z,fs_isop
    cp      '-'
    jr      z,fs_isop
    cp      '*'
    jr      z,fs_isop
    cp      '/'
    jr      nz,fs_done
fs_isop:
    inc     hl
fs_sp2:
    ld      a,(hl)
    cp      ' '
    jr      nz,fs_n2
    inc     hl
    jr      fs_sp2
fs_n2:
    call    isdigit
    jr      nc,fs_done
    call    parse_num
    inc     b
    jr      fs_group
fs_done:
    pop     hl
    ld      a,b
    or      a
    jr      z,fs_fail
    ld      (sumptr),hl
    ld      (sumend),de
    ret
fs_fail:
    inc     hl
    jr      fs_try

parse_num:                      ; HL at a digit -> HL behind the number
    inc     hl
    ld      a,(hl)
    call    isdigit
    jr      c,parse_num
    cp      '.'
    ret     nz
    inc     hl
    ld      a,(hl)
    call    isdigit
    jr      c,pn_frac
    dec     hl                  ; a full stop, not a decimal point
    ret
pn_frac:
    inc     hl
    ld      a,(hl)
    call    isdigit
    jr      c,pn_frac
    ret

isdigit:                        ; carry if A is a digit; A is kept
    cp      '0'
    ccf
    ret     nc
    cp      '9'+1
    ret

isletter:                       ; carry if A is a letter
    cp      $80
    jr      nc,il_no
    push    hl
    ld      hl,charmap
    add     a,l
    ld      l,a
    jr      nc,ASMPC+3
    inc     h
    ld      a,(hl)
    pop     hl
    sub     2                   ; symbols 2..27 are a..z
    cp      26
    ret
il_no:
    or      a
    ret

; ---- the answer ------------------------------------------------------------------
; A = its number.  Marks in the text: $10 default $11 = the number of the line or
; the default; $12 default $11 = the sum or the default; $13 .. $14 = only if
; there is a number; $15 = the number.
print_answer:
    ld      l,a
    ld      h,0
    add     hl,hl
    ld      de,anstab
    add     hl,de
    ld      e,(hl)
    inc     hl
    ld      d,(hl)
    ld      hl,answers
    add     hl,de
pa_loop:
    ld      a,(hl)
    inc     hl
    or      a
    ret     z
    cp      $10
    jr      c,pa_char
    cp      $16
    jr      nc,pa_char
    sub     $10
    jr      z,pa_num
    dec     a
    jr      z,pa_loop           ; $11: the end of a default that was printed
    dec     a
    jr      z,pa_sum
    dec     a
    jr      z,pa_opt
    dec     a
    jr      z,pa_loop           ; $14
    call    put_number          ; $15
    jr      pa_loop
pa_char:
    push    hl
    call    putc
    pop     hl
    jr      pa_loop
pa_num:
    ld      a,(numlen)
    or      a
    jr      z,pa_loop           ; no number: the default follows
    call    put_number
pa_skip:
    ld      a,(hl)
    inc     hl
    cp      $11
    jr      nz,pa_skip
    jr      pa_loop
pa_sum:
    ld      de,(sumptr)
    ld      a,d
    or      e
    jr      z,pa_loop
    call    put_sum
    jr      pa_skip
pa_opt:
    ld      a,(numlen)
    or      a
    jr      nz,pa_loop
pa_skipopt:
    ld      a,(hl)
    inc     hl
    cp      $14
    jr      nz,pa_skipopt
    jr      pa_loop

put_number:
    push    hl
    ld      hl,(numptr)
    ld      a,(numlen)
    ld      b,a
pn_loop:
    ld      a,(hl)
    push    hl
    push    bc
    call    putc
    pop     bc
    pop     hl
    inc     hl
    djnz    pn_loop
    pop     hl
    ret

put_sum:                        ; the sum without its spaces
    push    hl
    ld      hl,(sumptr)
ps_loop:
    ld      de,(sumend)
    ld      a,l
    cp      e
    jr      nz,ps_char
    ld      a,h
    cp      d
    jr      z,ps_end
ps_char:
    ld      a,(hl)
    inc     hl
    cp      ' '
    jr      z,ps_loop
    push    hl
    call    putc
    pop     hl
    jr      ps_loop
ps_end:
    pop     hl
    ret

; ---- text out ----------------------------------------------------------------------
puts:
    ld      a,(hl)
    or      a
    ret     z
    push    hl
    call    putc
    pop     hl
    inc     hl
    jr      puts

; Words are kept back until they are complete, so that a line never breaks
; inside a word.  Codes 1..6 are the letters the ROM font lacks.
putc:
    cp      13
    jr      z,pc_flush_nl
    cp      ' '
    jr      z,pc_space
    ld      hl,wordlen
    ld      e,(hl)
    ld      d,0
    inc     (hl)
    ld      hl,wordbuf
    add     hl,de
    ld      (hl),a
    ld      a,e
    cp      COLUMNS-2
    ret     c
    jr      pc_flush            ; a very long word: print what there is
pc_space:
    call    pc_flush
    ld      a,(column)
    or      a
    ret     z                   ; no space at the start of a line
    cp      COLUMNS
    jr      nc,pc_wrapped
    ld      a,' '
    jr      pc_out
pc_flush_nl:
    call    pc_flush
    ld      a,(column)
    cp      COLUMNS
    jr      nc,pc_wrapped       ; the ROM has already moved to the next line
pc_newline:
    ld      a,13
    call    ROM_PUTC
pc_wrapped:
    xor     a
    ld      (column),a
    ret
pc_flush:
    ld      a,(wordlen)
    or      a
    ret     z
    ld      b,a
    ld      a,(column)
    cp      COLUMNS
    jr      c,pc_room
    xor     a                   ; line exactly full: the ROM wrapped by itself
    ld      (column),a
pc_room:
    add     a,b
    cp      COLUMNS+1
    jr      c,pc_fits
    push    bc
    call    pc_newline
    pop     bc
pc_fits:
    ld      hl,wordbuf
pc_fl:
    ld      a,(hl)
    push    hl
    push    bc
    call    pc_out
    pop     bc
    pop     hl
    inc     hl
    djnz    pc_fl
    xor     a
    ld      (wordlen),a
    ret
pc_out:
    ld      hl,column
    inc     (hl)
    cp      8
    jp      nc,ROM_PUTC
    add     a,$7F               ; 1..6 -> $80..$85: our own glyphs
    jp      ROM_PUTC

; ---- variables -----------------------------------------------------------------
nsym:       defb 0
ngram:      defb 0
count:      defb 0
seed:       defw 0
fpos:       defw 0
cptr:       defw 0
best:       defb 0
second:     defw 0
unsure:     defb 0
numptr:     defw 0
numlen:     defb 0
sumptr:     defw 0
sumend:     defw 0
column:     defb 0
wordlen:    defb 0
wordbuf:    defs COLUMNS

; Glyphs in the ROM's format: 6 pixels in bits 6..1, bit 7 = skip two rows
; first, bit 0 = last row.  i-acute, I-acute, O-acute, O-double-acute,
; U-acute, U-double-acute.
font:
    defb    $08,$10,$80,$30,$10,$10,$10,$39
    defb    $10,$38,$10,$10,$10,$10,$10,$39
    defb    $10,$38,$44,$44,$44,$44,$44,$39
    defb    $14,$38,$44,$44,$44,$44,$44,$39
    defb    $10,$44,$44,$44,$44,$44,$44,$39
    defb    $14,$44,$44,$44,$44,$44,$44,$39

; ---- the network and the texts ----------------------------------------------------
title:      binary "title.bin"
hedge:      binary "hedge.bin"
dlevels:    binary "dlevels.bin"
charmap:    binary "charmap.bin"
bias:       binary "bias.bin"
anstab:     binary "anstab.bin"
    align   256
tanh:       binary "tanh.bin"
ocodes:     binary "ocodes.bin"
table:      binary "table.bin"
answers:    binary "answers.bin"
image_end:
