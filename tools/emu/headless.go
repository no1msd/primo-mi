// Headless driver for the PrimGO PRIMO emulator core.
//
// It reuses PrimGO's `primo` package (memory map, ROMs, IO ports, tape player)
// and the same per-frame emulation loop as PrimGO's main.go, but replaces the
// Ebitengine window with a scripted timeline: no window, no audio device, no X
// server.  Frames go to a raw RGB24 file, the speaker bit goes to a WAV file,
// and screenshots are written as PNG.
//
// This file is copied into third_party/primgo/cmd/headless by setup.sh so that
// it can import the (non-go-gettable) "primgo/primo" package.
package main

import (
	"bufio"
	"encoding/binary"
	"flag"
	"fmt"
	"image"
	"image/png"
	"os"
	"sort"
	"strconv"
	"strings"

	"github.com/koron-go/z80"

	"primgo/primo"
)

const (
	tickPerSec   = 50
	vblankLength = 0.0016
	sampleRate   = 44100
)

// PRIMO keyboard matrix addresses (IN port number == key number).
var keyNames = map[string]uint8{
	"Y": 0x00, "UP": 0x01, "S": 0x02, "SHIFT": 0x03, "E": 0x04, "UPPER": 0x05,
	"W": 0x06, "CTR": 0x07, "D": 0x08, "3": 0x09, "X": 0x0a, "2": 0x0b,
	"Q": 0x0c, "1": 0x0d, "A": 0x0e, "DOWN": 0x0f, "C": 0x10, "F": 0x12,
	"R": 0x14, "T": 0x16, "7": 0x17, "H": 0x18, "SPACE": 0x19, "B": 0x1a,
	"6": 0x1b, "G": 0x1c, "5": 0x1d, "V": 0x1e, "4": 0x1f, "N": 0x20,
	"8": 0x21, "Z": 0x22, "+": 0x23, "U": 0x24, "0": 0x25, "J": 0x26,
	"<": 0x27, "L": 0x28, "-": 0x29, "K": 0x2a, ".": 0x2b, "M": 0x2c,
	"9": 0x2d, "I": 0x2e, ",": 0x2f, "P": 0x32, "O": 0x34, "CLS": 0x35,
	"RETURN": 0x37, "ENTER": 0x37, "LEFT": 0x39, "RIGHT": 0x3d, "BRK": 0x3f,
}

type emulator struct {
	mem   *primo.Memory
	io    *primo.IO
	tape  *primo.TapePlayer
	cpu   *z80.CPU
	clock int

	ramInitialized bool
	frame          int
	cycles         int64 // T-states executed since power-on
	lastHit        map[uint16]int64
	held           map[uint8]bool

	audioAcc float64
	wav      []int16
	video    *bufio.Writer
	rec      bool

	pcHist  []uint32
	breakAt map[uint16]string
	hits    map[uint16]int
	maxHits int
}

// patchPTPLoad mirrors PrimGO's Emulator.patchPTPLoad.
func (e *emulator) patchPTPLoad() {
	if e.cpu.PC == e.mem.ROMLabelAddress(primo.ROMLabelRDSYN) {
		e.cpu.PC += 8
	}
	if e.cpu.PC == e.mem.ROMLabelAddress(primo.ROMLabelINBYTE) {
		b := e.tape.NextByte()
		e.cpu.DE.Hi = b + e.cpu.DE.Hi
		e.cpu.AF.Hi = b
		e.cpu.PC += 13
	}
	if e.cpu.PC == e.mem.ROMLabelAddress(primo.ROMLabelRDHEAD)+9 {
		e.cpu.PC += 110
	}
}

func (e *emulator) patchNMI() {
	if e.mem.ROMType == primo.ROMTypeC {
		if e.cpu.PC == e.mem.ROMLabelAddress(primo.ROMLabelNMIStuck) {
			e.cpu.PC++
		}
		return
	}
	if e.cpu.PC == e.mem.ROMLabelAddress(primo.ROMLabelRESET) {
		e.cpu.InNMI = false
	}
}

// tick emulates one 1/50 s frame, exactly like PrimGO's Emulator.Update.
func (e *emulator) tick() {
	keys := make([]uint8, 0, len(e.held))
	for k := range e.held {
		keys = append(keys, k)
	}
	e.io.Keys = keys

	vblankCycles := int(vblankLength * float64(e.clock))
	cyclesPerTick := e.clock / tickPerSec
	if e.ramInitialized {
		e.io.NMINext = true
	}
	sampleCycles := float64(e.clock) / sampleRate
	for i := 0; i < cyclesPerTick; i += e.cpu.LastOpCycles {
		e.io.VBlank = i < vblankCycles
		pc := e.cpu.PC
		if pc == e.mem.ROMLabelAddress(primo.ROMLabelINIT) {
			e.ramInitialized = true
		}
		e.patchPTPLoad()
		e.patchNMI()

		e.audioAcc += float64(e.cpu.LastOpCycles)
		if e.audioAcc > sampleCycles {
			e.audioAcc -= sampleCycles
			if e.rec {
				if e.io.Speaker {
					e.wav = append(e.wav, 0x3000)
				} else {
					e.wav = append(e.wav, -0x3000)
				}
			}
		}
		if e.pcHist != nil {
			e.pcHist[e.cpu.PC]++
		}
		if len(e.breakAt) > 0 {
			if name, ok := e.breakAt[e.cpu.PC]; ok {
				e.hits[e.cpu.PC]++
				if e.hits[e.cpu.PC] <= e.maxHits {
					sp := e.cpu.SP
					fmt.Printf("[f%05d] hit %s pc=%04x af=%02x%02x bc=%04x de=%04x hl=%04x sp=%04x stk=%04x %04x %04x %04x T=%d dT=%d\n",
						e.frame, name, e.cpu.PC, e.cpu.AF.Hi, e.cpu.AF.Lo, e.cpu.BC.U16(), e.cpu.DE.U16(), e.cpu.HL.U16(), sp,
						e.w16(sp), e.w16(sp+2), e.w16(sp+4), e.w16(sp+6), e.cycles, e.cycles-e.lastHit[e.cpu.PC])
				}
				e.lastHit[e.cpu.PC] = e.cycles
			}
		}
		e.cpu.Step()
		e.cycles += int64(e.cpu.LastOpCycles)
	}
	e.frame++
	if e.rec && e.video != nil {
		e.video.Write(e.rgb())
	}
}

func (e *emulator) w16(a uint16) uint16 {
	return uint16(e.mem.Get(a)) | uint16(e.mem.Get(a+1))<<8
}

func (e *emulator) page() primo.ScreenPage {
	if e.io.PrimaryVideo {
		return primo.ScreenPagePrimary
	}
	return primo.ScreenPageSecondary
}

func (e *emulator) rgb() []byte {
	rgba := e.mem.GetRGBAScreenData(e.page())
	out := make([]byte, len(rgba)/4*3)
	for i, j := 0, 0; i < len(rgba); i, j = i+4, j+3 {
		out[j], out[j+1], out[j+2] = rgba[i], rgba[i+1], rgba[i+2]
	}
	return out
}

func (e *emulator) shot(path string, scale int) error {
	size := e.mem.ScreenResolution(e.page())
	rgba := e.mem.GetRGBAScreenData(e.page())
	img := image.NewRGBA(image.Rect(0, 0, size.X*scale, size.Y*scale))
	for y := 0; y < size.Y*scale; y++ {
		for x := 0; x < size.X*scale; x++ {
			s := ((y/scale)*size.X + x/scale) * 4
			d := img.PixOffset(x, y)
			copy(img.Pix[d:d+4], rgba[s:s+4])
		}
	}
	f, err := os.Create(path)
	if err != nil {
		return err
	}
	defer f.Close()
	return png.Encode(f, img)
}

func (e *emulator) run(n int) {
	for i := 0; i < n; i++ {
		e.tick()
	}
}

func (e *emulator) press(k uint8, hold, gap int) {
	e.held[k] = true
	e.run(hold)
	delete(e.held, k)
	e.run(gap)
}

func (e *emulator) typeText(s string, hold, gap int) {
	for _, r := range strings.ToUpper(s) {
		name := string(r)
		switch r {
		case ' ':
			name = "SPACE"
		case '\n':
			name = "RETURN"
		}
		k, ok := keyNames[name]
		if !ok {
			fmt.Fprintf(os.Stderr, "cannot type %q\n", r)
			continue
		}
		e.press(k, hold, gap)
	}
}

func parseKey(s string) (uint8, error) {
	if k, ok := keyNames[strings.ToUpper(s)]; ok {
		return k, nil
	}
	v, err := strconv.ParseUint(s, 0, 8)
	return uint8(v), err
}

func parseAddr(s string) uint16 {
	v, err := strconv.ParseUint(strings.TrimPrefix(strings.ToLower(s), "0x"), 16, 16)
	if err != nil {
		fmt.Fprintf(os.Stderr, "bad address %q\n", s)
		os.Exit(2)
	}
	return uint16(v)
}

func writeWAV(path string, samples []int16) error {
	f, err := os.Create(path)
	if err != nil {
		return err
	}
	defer f.Close()
	w := bufio.NewWriter(f)
	defer w.Flush()
	dataLen := uint32(len(samples) * 2)
	w.WriteString("RIFF")
	binary.Write(w, binary.LittleEndian, 36+dataLen)
	w.WriteString("WAVEfmt ")
	binary.Write(w, binary.LittleEndian, uint32(16))
	binary.Write(w, binary.LittleEndian, uint16(1))
	binary.Write(w, binary.LittleEndian, uint16(1))
	binary.Write(w, binary.LittleEndian, uint32(sampleRate))
	binary.Write(w, binary.LittleEndian, uint32(sampleRate*2))
	binary.Write(w, binary.LittleEndian, uint16(2))
	binary.Write(w, binary.LittleEndian, uint16(16))
	w.WriteString("data")
	binary.Write(w, binary.LittleEndian, dataLen)
	return binary.Write(w, binary.LittleEndian, samples)
}

func main() {
	ptp := flag.String("ptp", "", "PTP tape image to insert")
	rom := flag.String("rom", "a", "ROM type: a, b or c")
	clock := flag.Int("clock", 2500000, "CPU clock in Hz")
	script := flag.String("script", "", "script file (default: stdin)")
	videoOut := flag.String("video", "", "raw RGB24 output for recorded frames")
	audioOut := flag.String("audio", "", "WAV output for recorded frames")
	pcHist := flag.String("pchist", "", "write executed-PC histogram (64K x uint32 LE)")
	breaks := flag.String("break", "", "comma separated hex PCs to log (name=addr or addr)")
	scale := flag.Int("scale", 3, "screenshot scale factor")
	maxHits := flag.Int("hits", 40, "how many hits of each -break address to log")
	flag.Parse()

	rt := primo.ROMType(*rom)
	if !rt.Validate() {
		fmt.Fprintln(os.Stderr, "invalid ROM type")
		os.Exit(2)
	}
	e := &emulator{
		mem:     primo.NewMemory(rt),
		io:      primo.NewIO(),
		tape:    primo.NewTapePlayer(),
		clock:   *clock,
		held:    map[uint8]bool{},
		breakAt: map[uint16]string{},
		hits:    map[uint16]int{},
		lastHit: map[uint16]int64{},
		maxHits: *maxHits,
	}
	e.cpu = z80.Build(z80.WithMemory(e.mem), z80.WithIO(e.io), z80.WithNMI(e.io))
	if *ptp != "" {
		data, err := os.ReadFile(*ptp)
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
		e.tape.ChangeTape(data)
	}
	if *pcHist != "" {
		e.pcHist = make([]uint32, 0x10000)
	}
	for _, b := range strings.Split(*breaks, ",") {
		if b == "" {
			continue
		}
		name, addr := b, b
		if i := strings.IndexByte(b, '='); i >= 0 {
			name, addr = b[:i], b[i+1:]
		}
		e.breakAt[parseAddr(addr)] = name
	}
	if *videoOut != "" {
		f, err := os.Create(*videoOut)
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
		defer f.Close()
		e.video = bufio.NewWriterSize(f, 1<<20)
		defer e.video.Flush()
	}

	in := os.Stdin
	if *script != "" {
		f, err := os.Open(*script)
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
		defer f.Close()
		in = f
	}

	hold, gap := 6, 4
	sc := bufio.NewScanner(in)
	for sc.Scan() {
		line := strings.TrimSpace(sc.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		cmd, arg, _ := strings.Cut(line, " ")
		arg = strings.TrimSpace(arg)
		f := strings.Fields(arg)
		switch cmd {
		case "wait":
			n, _ := strconv.Atoi(arg)
			e.run(n)
		case "type":
			e.typeText(strings.ReplaceAll(arg, `\n`, "\n"), hold, gap)
		case "speed":
			hold, _ = strconv.Atoi(f[0])
			gap, _ = strconv.Atoi(f[1])
		case "press":
			k, err := parseKey(f[0])
			if err != nil {
				fmt.Fprintln(os.Stderr, "bad key", f[0])
				os.Exit(2)
			}
			n := hold
			if len(f) > 1 {
				n, _ = strconv.Atoi(f[1])
			}
			e.press(k, n, 0)
		case "down", "up":
			for _, name := range f {
				k, err := parseKey(name)
				if err != nil {
					fmt.Fprintln(os.Stderr, "bad key", name)
					os.Exit(2)
				}
				if cmd == "down" {
					e.held[k] = true
				} else {
					delete(e.held, k)
				}
			}
		case "shot":
			if err := e.shot(arg, *scale); err != nil {
				fmt.Fprintln(os.Stderr, err)
				os.Exit(1)
			}
		case "rec":
			e.rec = arg == "on"
		case "dump":
			buf := make([]byte, 0x10000)
			for i := range buf {
				buf[i] = e.mem.Get(uint16(i))
			}
			os.WriteFile(arg, buf, 0o644)
		case "poke":
			a := parseAddr(f[0])
			for i, v := range f[1:] {
				b, _ := strconv.ParseUint(v, 16, 8)
				e.mem.Set(a+uint16(i), uint8(b))
			}
		case "peek":
			a := parseAddr(f[0])
			n := 1
			if len(f) > 1 {
				n, _ = strconv.Atoi(f[1])
			}
			fmt.Printf("[f%05d] %04x:", e.frame, a)
			for i := 0; i < n; i++ {
				fmt.Printf(" %02x", e.mem.Get(a+uint16(i)))
			}
			fmt.Println()
		case "state":
			fmt.Printf("[f%05d] pc=%04x sp=%04x af=%02x%02x bc=%04x de=%04x hl=%04x page=%s nmi=%v\n",
				e.frame, e.cpu.PC, e.cpu.SP, e.cpu.AF.Hi, e.cpu.AF.Lo, e.cpu.BC.U16(), e.cpu.DE.U16(), e.cpu.HL.U16(),
				e.page(), e.io.NMIEnabled)
		case "echo":
			fmt.Printf("[f%05d] %s\n", e.frame, arg)
		default:
			fmt.Fprintf(os.Stderr, "unknown command %q\n", cmd)
			os.Exit(2)
		}
	}

	if *audioOut != "" {
		if err := writeWAV(*audioOut, e.wav); err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
	}
	if e.pcHist != nil {
		f, _ := os.Create(*pcHist)
		binary.Write(f, binary.LittleEndian, e.pcHist)
		f.Close()
	}
	if len(e.hits) > 0 {
		addrs := make([]int, 0, len(e.hits))
		for a := range e.hits {
			addrs = append(addrs, int(a))
		}
		sort.Ints(addrs)
		for _, a := range addrs {
			fmt.Printf("hits %-12s %04x: %d\n", e.breakAt[uint16(a)], a, e.hits[uint16(a)])
		}
	}
}
