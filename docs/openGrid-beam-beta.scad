// openGrid-beam-refactored.scad
// -------------------------------------------------------------------
// OpenGrid Beam & Corner Library (enum-based, BOSL2-style)
// -------------------------------------------------------------------

include <BOSL2/std.scad>;
use <QuackWorks/openGrid/openGrid.scad>;

// ==========================================================
// 0. OpenGrid Basis-Parameter (wie bisher)
// ==========================================================

/*[Board Type]*/
Full_or_Lite = "Lite"; //[Full, Lite, Heavy]
Board_Width  = 2;
Board_Height = 2;

/*[OpenGrid - Tile]*/
Tile_Size            = 28;
Tile_Thickness       = 6.8;
Lite_Tile_Thickness  = 4;
Heavy_Tile_Thickness = 13.8;
Heavy_Tile_Gap       = 0.2;
Intersection_Distance = 4.2; // Chamfer-Länge

/*[OpenGrid - Connector]*/
connector_cutout_radius        = 2.6;
connector_cutout_dimple_radius = 2.7;
connector_cutout_separation    = 2.5;
connector_cutout_height        = 2.4;
lite_cutout_distance_from_top  = 1;

/*[OpenGrid - border]*/
Connector_Tolerance  = 0.05;

// ----------------------------------------------------------
// Derived
// ----------------------------------------------------------

th =
    Full_or_Lite == "Lite"  ? Lite_Tile_Thickness :
    Full_or_Lite == "Heavy" ? Heavy_Tile_Thickness :
    Tile_Thickness;

hypthenuse = sqrt(2*Intersection_Distance*Intersection_Distance);

cut_distance_to_top =
    (th == Lite_Tile_Thickness)
        ? (lite_cutout_distance_from_top + connector_cutout_height/2)
        : (th / 2);

connector_length_half = connector_cutout_radius + connector_cutout_separation;

leg_len = th + connector_length_half;

back_offset  = th / sqrt(2);
front_offset = connector_length_half / sqrt(2);

bottom_to_top = (leg_len*2 / sqrt(2) - back_offset - front_offset);

extension = Tile_Size / 2 - Intersection_Distance;

// ==========================================================
// 1. ENUMS / User-Parameter
// ==========================================================

/*[Beam Side Modes]*/
BeamMode_Bottom = "beam"; //[none, beam, board]
BeamMode_Left   = "beam"; //[none, beam, board]
BeamMode_Top    = "beam"; //[none, beam, board]
BeamMode_Right  = "beam"; //[none, beam, board]

/*[Reach Options]*/
Reach_Mode      = "none";      //[none, halftile, segments]
Reach_Value     = 1;           // used when Reach_Mode="segments"
Reach_Direction = "auto";      //[auto, inward, outward]

/*[Global Beam Options]*/
Beam_Extension_Factor = 0.5;  // 0..1 Anteil Segmentlänge pro Ende ohne Joint/Chamfer
Print_Mode            = false; // true = flach zum Drucken
Print_EndParts_Mode   = "attached"; // ["attached", "separate"]

// ==========================================================
// 2. Corner-Konfiguration (ENUM / spin / orient)
// ==========================================================

/*[Corner BL]*/
CornerBL_Type           = "none";      //[joint, chamfer, shorten, none]
CornerBL_Attach         = "none";       //[none, horizontal, vertical]
CornerBL_BoardConnector = "tileside";   //[none, tileside, offtileside]
CornerBL_Spin           = 0;
CornerBL_Orient         = UP;

/*[Corner BR]*/
CornerBR_Type           = "none";
CornerBR_Attach         = "none";
CornerBR_BoardConnector = "tileside";
CornerBR_Spin           = 90;
CornerBR_Orient         = DOWN;

/*[Corner TL]*/
CornerTL_Type           = "none";
CornerTL_Attach         = "none";
CornerTL_BoardConnector = "tileside";
CornerTL_Spin           = 90;
CornerTL_Orient         = DOWN;

/*[Corner TR]*/
CornerTR_Type           = "none";
CornerTR_Attach         = "none";
CornerTR_BoardConnector = "tileside";
CornerTR_Spin           = 0;
CornerTR_Orient         = UP;

// ==========================================================
// 3. Helper-Funktionen / Corner-Helpers
// ==========================================================

function clamp01(x) = x < 0 ? 0 : (x > 1 ? 1 : x);

function beam_side_is_horizontal(side) =
    (side == "bottom" || side == "top");

function beam_side_is_vertical(side) =
    (side == "left" || side == "right");

// Attach type helpers
function corner_attach_is_horizontal(kind) =
    (kind == "horizontal");

function corner_attach_is_vertical(kind) =
    (kind == "vertical");

// Boardconnector?
function corner_has_boardconnector(mode) =
    (mode == "tileside" || mode == "offtileside");

// Corner-Struct als Vektor [type, attach, boardconn, spin, orient]
function corner_cfg(type, attach, bconn, spin, orient) =
    [type, attach, bconn, spin, orient];

function corner_type(cfg)           = cfg[0];
function corner_attach(cfg)         = cfg[1];
function corner_boardconn(cfg)      = cfg[2];
function corner_spin(cfg)           = cfg[3];
function corner_orient(cfg)         = cfg[4];

// =========================================
// Corner-Konfiguration als Vektor
// =========================================

CornerBL = [CornerBL_Type, CornerBL_Attach, CornerBL_BoardConnector, CornerBL_Spin, CornerBL_Orient];
CornerBR = [CornerBR_Type, CornerBR_Attach, CornerBR_BoardConnector, CornerBR_Spin, CornerBR_Orient];
CornerTL = [CornerTL_Type, CornerTL_Attach, CornerTL_BoardConnector, CornerTL_Spin, CornerTL_Orient];
CornerTR = [CornerTR_Type, CornerTR_Attach, CornerTR_BoardConnector, CornerTR_Spin, CornerTR_Orient];

// hilfsfunktion: Corner für Seite + Start/End liefern
// side: "bottom", "top", "left", "right"
// at_start: true = start, false = end

function corner_cfg_for_side(side, at_start) =
    (side == "bottom") ? (at_start ? CornerBL : CornerBR) :
    (side == "top")    ? (at_start ? CornerTL : CornerTR) :
    (side == "left")   ? (at_start ? CornerTL : CornerBL) :
                         (at_start ? CornerBR : CornerTR);

// nur EIN Beam "besitzt" die Geometrie an der Ecke,
// damit Joints/Chamfers nicht doppelt gezeichnet werden.
//
// Vereinbarung:
//  - BL & BR gehören geometrisch dem BOTTOM-Beam
//  - TL & TR gehören geometrisch dem TOP-Beam
//
// LEFT/RIGHT sehen die Corner-Zustände (attach etc.), bekommen
// aber KEINE Joint-/Chamfer-Geometrie.
function corner_owner(side, at_start) =
    (side == "bottom") ? true :        // BL & BR → bottom
    (side == "top")    ? true :        // TL & TR → top
                         false;

// Corner-Typ in einem cfg-Vektor überschreiben
function corner_with_type(cfg, new_type) =
    [ new_type, cfg[1], cfg[2], cfg[3], cfg[4] ];
    


// Overhang-Offset entlang Normal (pro Seite)
function reach_amount(mode, value) =
    mode == "halftile" ? (Tile_Size/2) :
    mode == "segments" ? (value * Tile_Size) :
    0;

function reach_sign(direction) =
    (direction == "inward")  ? -1 :
    (direction == "outward") ?  1 :
    1; // auto = outward

// ==========================================================
// 4. Geometrie-Basis (aus deiner Datei, leichte Kosmetik)
// ==========================================================

// 4.1 2D-Basisformen

module legs_2d() {
    union() {
        square([leg_len, th], center=false);
        square([th, leg_len], center=false);
    }
}

module triangle_substract() {
    polygon(points = [
        [0,   0],
        [0,   th],
        [th,  0]
    ]);
}

module triangle_fill() {
    polygon(points = [
        [th,      th     ],
        [leg_len, th     ],
        [th,      leg_len]
    ]);
}

module base_body_2d() {
    difference() {
        legs_2d();
        triangle_substract();
    }
    triangle_fill();
}

module base_body(h) {
    linear_extrude(height = h)
        base_body_2d();
}

// 4.2 Corner-Joint/Chamfer (deine Geometrie unverändert übernommen)

module joint_leg_segment(d, apply_cutout) { 
    should_cut = apply_cutout;

    difference() {      
        union() {
            base_body(d);
            translate([0, 0, -Intersection_Distance])
                base_body(d);
        }
        if (should_cut) cut_out();
    }
}

module cut_out() {
    rotate([45,-90,0])
        translate([-Intersection_Distance+connector_cutout_radius-Connector_Tolerance,
                   0,
                   -bottom_to_top])
            connector_cutout_delete_tool(); 
}

module joint_leg_connector(d,e) {
    base_body(d);
    translate([0, 0, -e])
        base_body(d);
}

module joint_raw_part() {
    xy_center = back_offset*2 + front_offset;
    P_xy      = -unit([1,1,0]) * xy_center;

    module joint_leg_group() {
        union() {
            joint_leg_segment(Intersection_Distance, false);

            translate(-P_xy + [connector_length_half/2, 0, 0]) {
                yrot(90)
                    translate(P_xy + [
                        -connector_length_half/2 - hypthenuse/sqrt(2),
                        0,
                        hypthenuse/sqrt(2)
                    ])
                    mirror([0,0,1])
                        joint_leg_segment(Intersection_Distance, true);      
            }
        }
    }

    module connector_group() {
        union() {
            translate(-P_xy + [connector_length_half/2, 0, 0]) {
                rotate(a = 45, v = [0, 1, 0])
                    translate(P_xy + [-connector_length_half/2, 0, 0])
                        joint_leg_connector(hypthenuse * 1.25, hypthenuse * 0.25);
            }

            translate(-P_xy + [sqrt(2)*2, sqrt(2)*2,
                               connector_length_half/2 + Intersection_Distance]) {
                rotate(a = 90, v = [1, 1, 0])
                    rotate(a = -45, v = [0, 0, 1])
                        translate(P_xy)
                            joint_leg_connector(hypthenuse * 0.75, 0);
            }
        }
    }

    module mirror_xy() {
        children();
        mirror([-1, 1, 0])
            children();
    }

    union() {
        mirror_xy()
            joint_leg_group();

        mirror_xy()
            connector_group();
    }
}

module joint_raw() {
    angle = 180 - acos(1 / sqrt(3));
    
    difference() {
        union() {
            joint_raw_part();
            hull() {
                intersection() { 
                    joint_raw_part();
                    translate([th + Intersection_Distance/2,
                               th + Intersection_Distance/2,
                               Intersection_Distance/2 + connector_length_half]) {
                        rotate(a = -angle, v = [1, -1, 0]) {
                            zrot(-15) {
                                zmove(0.5)
                                    intersection() {
                                        regular_prism(3, r=th/2+connector_length_half+1, h=7, center = true);
                                        zrot(60)
                                            regular_prism(3, r=th/2+connector_length_half+1, h=7, center = true);
                                    }
                                zmove(-leg_len/2)
                                    regular_prism(3, r=leg_len+3.5, h=leg_len/2, center = false);
                            }
                        }
                    }
                }
            }
        }
        translate([th + Intersection_Distance/2,
                   th + Intersection_Distance/2,
                   Intersection_Distance/2 + connector_length_half]) {
            rotate(a = -angle, v = [1, -1, 0]) {
                zmove((-4*(0.6*th/4))-1.4)
                    cylinder(h = 4, r = th*3, center = true);
            }
        }
    }
}

module chamfers() {
    difference() {
        joint_raw();
        translate([0, -20, Intersection_Distance-Connector_Tolerance])
            cube([40, 40, 40], center=false);
    }
}

// 4.3 Segment (Beam-Kern, extrudiertes L-Profil)

module segment(seg_len, cutouts_enabled = true) {
    if (cutouts_enabled) {
        difference() {
            base_body(seg_len);
            translate([cut_distance_to_top,
                       th + connector_length_half/2 + Connector_Tolerance/100,
                       seg_len/2])
                rotate([90, 180, 90])
                    connector_cutout_delete_tool();
            translate([th + connector_length_half/2 + Connector_Tolerance/100,
                       cut_distance_to_top,
                       seg_len/2])
                rotate([90, 0, 180])
                    connector_cutout_delete_tool();
        }
    } else {
        base_body(seg_len);
    }
}

// ==========================================================
// 5. Corner-Parts als BOSL2-attachable (spin/orient nutzbar)
//    → Joint/Chamfer werden so verschoben, dass die
//      Kontaktfläche bei z=0 liegt (wie früher).
// ==========================================================

module corner_part3d(type="joint",
                     anchor=CENTER,
                     spin=0,
                     orient=UP) {

    // grobe size-Schätzung (für attachable)
    size_est = [leg_len*2, leg_len*2, leg_len*2];

    attachable(anchor, spin, orient, size=size_est) {

        // Anker: verschiebt joint_raw/chamfers so, dass die
        // Kontaktfläche exakt bei z=0 liegt.
        translate([0, 0, Intersection_Distance]) {
            if (type == "joint")
                joint_raw();
            else if (type == "chamfer")
                chamfers();
        }

        children();
    }
}



// ==========================================================
// 6. Beam-Tile: ein Segment + optionale Corner-Parts
// ==========================================================
//
// - is_start / is_end: true beim ersten/letzten Segment einer Seite
// - corner_start_cfg / corner_end_cfg: Corner-Structs
// - side: "bottom", "left", "top", "right"
// - beammode: "none", "beam", "board"
//

// ==========================================================
// Beam-Segment mit Endkappen (neutral, kein Print-Mode hier)
// ==========================================================
module beam_tile(
    side,                       // "bottom", "top", "left", "right"
    is_start = false,
    is_end   = false,
    
    // Corner-Konfigurationen (struct-ähnliche Arrays oder was du verwendest)
    corner_start_cfg,
    corner_end_cfg,

    // Beam-Typ auf dieser Seite: "none", "beam", "board"
    beammode           = "beam",

    // Cutouts entlang des Beams?
    beam_cutouts       = true,

    // optionale Kürzung am Start/Ende (0..1)
    shorten_factor_start = 0,
    shorten_factor_end   = 0
) {
    
    segment_length = Tile_Size;
    extension_base = extension;

    // Lokaler Joint/Chamfer-Typ aus Corner-Config lesen
    type_start   = corner_start_cfg[0];   // "joint", "chamfer", "shorten", "none"
    type_end     = corner_end_cfg[0];

    attach_start = corner_start_cfg[1];   // "none", "horizontal", "vertical"
    attach_end   = corner_end_cfg[1];

    boardconn_start = corner_start_cfg[2]; // "none", "tileside", "offtileside"
    boardconn_end   = corner_end_cfg[2];

    spin_start   = corner_start_cfg[3];
    orient_start = corner_start_cfg[4];

    spin_end     = corner_end_cfg[3];
    orient_end   = corner_end_cfg[4];

    // Helper: ist hier Joint/Chamfer aktiv?
    joint_start_on   = (type_start == "joint");
    chamfer_start_on = (type_start == "chamfer");
    shorten_start_on = (type_start == "shorten");

    joint_end_on   = (type_end == "joint");
    chamfer_end_on = (type_end == "chamfer");
    shorten_end_on = (type_end == "shorten");
    
    // Spiegelkorrektur: TL & BR (also Seiten top + right) brauchen Mirror
    mirror_joint = (side == "top") || (side == "right");

    // zentrale Länge
    do_shorten_start =
        (joint_start_on   && is_start) ||
        (chamfer_start_on && is_start) ||
        (shorten_start_on && is_start) ||
        (shorten_factor_start > 0);

    do_shorten_end =
        (joint_end_on   && is_end) ||
        (chamfer_end_on && is_end) ||
        (shorten_end_on && is_end) ||
        (shorten_factor_end > 0);

    extension_start = do_shorten_start
        ? max(extension_base - Intersection_Distance, 0)
        : segment_length * Beam_Extension_Factor;

    extension_end   = do_shorten_end
        ? max(extension_base - Intersection_Distance, 0)
        : segment_length * Beam_Extension_Factor;

    // Board-Connector-Cutouts in den Verlängerungen?
    // Attach = Joint direkt angeflanscht → keine Connector-Cutouts.
    boardconn_has_start =
        (boardconn_start == "tileside" || boardconn_start == "offtileside")
        && (attach_start == "none");

    boardconn_has_end   =
        (boardconn_end   == "tileside" || boardconn_end   == "offtileside")
        && (attach_end == "none");


    tile_side_start = (boardconn_start == "tileside");
    tile_side_end   = (boardconn_end   == "tileside");

    // --- Lokale Helfer ---

    module extension_with_cutouts(len, face_to_start=true, use_tileside=true) {
        if (len > 0)
            difference() {
                base_body(len);

                // vereinfachter Board-Connector: wir nehmen dein bestehendes
                // connector_cutout_delete_tool und drehen ihn passend
                cut_z = face_to_start
                    ? (connector_length_half / 2)
                    : (len - connector_length_half / 2);

                rot_y = face_to_start ? (-90) : (90);

                translate(unit([1,1,0]) * (bottom_to_top) + [0,0,cut_z])
                    rotate([0,rot_y,45])
                        translate([-Connector_Tolerance/100,0,0])
                            connector_cutout_delete_tool();
            }
    }

    // Endkappen + Joint/Chamfer aufbauen
    module beam_with_endcaps() {

        // zentrales Segment
        if (beammode != "none") {
            if (beam_cutouts)
                down(segment_length / 2)
                    segment(segment_length, cutouts_enabled = true);
            else
                down(segment_length / 2)
                    segment(segment_length, cutouts_enabled = false);
        }

        // Startverlängerung
        if (beammode != "none" && is_start)
            translate([0, 0, -segment_length / 2 - extension_start]) {
                if (boardconn_has_start)
                    extension_with_cutouts(extension_start, face_to_start=true, use_tileside=tile_side_start);
                else
                    base_body(extension_start);
            }

        // Endverlängerung
        if (beammode != "none" && is_end)
            translate([0, 0, segment_length / 2]) {
                if (boardconn_has_end)
                    extension_with_cutouts(extension_end, face_to_start=false, use_tileside=tile_side_end);
                else
                    base_body(extension_end);
            }

        // Start-Joint/Chamfer (mit spin/orient der Corner)
        if (is_start && (joint_start_on || chamfer_start_on))
            translate([0, 0, -segment_length / 2 - extension_start])
                corner_part3d(
                    type   = type_start,
                    spin   = spin_start,
                    orient = orient_start
                );

        // End-Joint/Chamfer (mit spin/orient der Corner)
        if (is_end && (joint_end_on || chamfer_end_on))
            translate([0, 0,  segment_length / 2 + extension_end])
                corner_part3d(
                    type   = type_end,
                    spin   = spin_end,
                    orient = orient_end
                );


    }

    // *** Hier KEIN Print_Mode! ***
    // beam_with_endcaps() bleibt im lokalen „Beam-Koordinatensystem“.
    // Die Einbettung in die Board-Geometrie (inkl. 45°-Schräge usw.)
    // passiert in den Side-Modulen.

    beam_with_endcaps();
}


// ==========================================================
// 7. Cutout-Tool aus openGrid (unverändert)
// ==========================================================

module connector_cutout_delete_tool(anchor = CENTER, spin = 0, orient = UP) {
    connector_cutout_radius        = 2.6;
    connector_cutout_dimple_radius = 2.7;
    connector_cutout_separation    = 2.5;
    connector_cutout_height        = 2.4;
    dimple_radius                  = 0.75 / 2;

    attachable(anchor, spin, orient,
               size=[connector_cutout_radius * 2 - 0.1,
                     connector_cutout_radius * 2,
                     connector_cutout_height]) {
        tag_scope()
            translate([-connector_cutout_radius + 0.05, 0, -connector_cutout_height / 2])
                render()
                    half_of(RIGHT, s=connector_cutout_dimple_radius * 4)
                        linear_extrude(height=connector_cutout_height)
                            union() {
                                left(0.1)
                                    diff() {
                                        $fn = 50;
                                        hull()
                                            xcopies(spacing=connector_cutout_radius * 2)
                                                circle(r=connector_cutout_radius);
                                        tag("remove")
                                            right(connector_cutout_radius - connector_cutout_separation)
                                                ycopies(spacing=(connector_cutout_radius + connector_cutout_separation) * 2)
                                                    circle(r=connector_cutout_dimple_radius);
                                    }
                                rect([1,
                                      connector_cutout_separation * 2
                                      - (connector_cutout_dimple_radius - connector_cutout_separation)],
                                     rounding=[0, -.25, -.25, 0],
                                     $fn=32, corner_flip=true, anchor=LEFT);
                            }
        children();
    }
}


// ==========================================================
// 8. Reach
// ==========================================================
//
/*
// Hilfsfunktionen für Segmentmittelpunkte
function hx(board_w, i) = (i + 0.5 - board_w/2) * Tile_Size;
function hy(board_h, j) = (j + 0.5 - board_h/2) * Tile_Size;
*/
//
// Jede Seite wird entlang ihrer Länge in Segmente aufgeteilt.
// Für Segment i gilt:
//   - is_start = (i == 0)
//   - is_end   = (i == last)
// Corner-Mapping erfolgt mit corner_for_side().
//
// Reach wirkt als zusätzlicher Offset entlang der Seitennormalen.
//
// Reach-Offset-Vektor pro Seite
function side_normal(side) =
    side == "bottom" ? [0,-1,0] :
    side == "top"    ? [0, 1,0] :
    side == "left"   ? [-1,0,0] :
                       [ 1,0,0];

function side_reach_offset(side) =
    let(a = reach_amount(Reach_Mode, Reach_Value),
        s = reach_sign(Reach_Direction))
        side_normal(side) * (a * s);
        
// ==========================================================
// 9. Side-Module (jede Seite separat, saubere Ausrichtung)
// ==========================================================

// Bottom: von BL nach BR
module side_bottom(board_w, board_h) {
    if (BeamMode_Bottom != "none" && board_w > 1)
    for (i = [0 : board_w-2]) {

        side     = "bottom";
        is_start = (i == 0);              // geometrisch: BL
        is_end   = (i == board_w-2);      // geometrisch: BR

        // --- WICHTIG: Bottom-Beam läuft lokal "andersrum"
        // → Start-End-Corner-Konfiguration vertauschen
        cfg_start_raw = corner_cfg_for_side(side, false); // BR
        cfg_end_raw   = corner_cfg_for_side(side, true);  // BL

        // Bottom ist Owner der BL/BR-Corner → Typen behalten
        cfg_start = corner_owner(side,true)
                    ? cfg_start_raw
                    : corner_with_type(cfg_start_raw, "none");

        cfg_end   = corner_owner(side,false)
                    ? cfg_end_raw
                    : corner_with_type(cfg_end_raw, "none");

        pos = [
            (i + 1 - board_w/2) * Tile_Size,
            -board_h * Tile_Size / 2,
            0
        ];

        translate(pos)
            // gleiche Ausrichtung wie bisher
            zrot(180)
            xrot(180)
            translate([0, -leg_len, 0])
            rotate([0, 90, 0])
                beam_tile(
                    side             = side,
                    is_start         = is_end,
                    is_end           = is_start,
                    corner_start_cfg = cfg_start,
                    corner_end_cfg   = cfg_end,
                    beammode         = BeamMode_Bottom,
                    beam_cutouts     = (BeamMode_Bottom == "beam")
                );
    }
}

// Top: von TL nach TR
module side_top(board_w, board_h) {
    if (BeamMode_Top != "none" && board_w > 1)
    for (i=[0:board_w-2]) {

        side     = "top";
        is_start = (i == 0);              // TL
        is_end   = (i == board_w-2);      // TR

        cfg_start_raw = corner_cfg_for_side(side, true);   // TL
        cfg_end_raw   = corner_cfg_for_side(side, false);  // TR

        // Top ist Corner-Owner
        cfg_start = corner_owner(side,true)
                    ? cfg_start_raw
                    : corner_with_type(cfg_start_raw, "none");

        cfg_end   = corner_owner(side,false)
                    ? cfg_end_raw
                    : corner_with_type(cfg_end_raw, "none");

        pos = [
            (i + 1 - board_w/2) * Tile_Size,
            board_h * Tile_Size / 2,
            0
        ];

        translate(pos)
            // Orientierung wie im alten openGridbeam (Top)
            xrot(180)
            translate([0, -leg_len, 0])
            rotate([0, 90, 0])
                beam_tile(
                    side             = side,
                    is_start         = is_start,
                    is_end           = is_end,
                    corner_start_cfg = cfg_start,
                    corner_end_cfg   = cfg_end,
                    beammode         = BeamMode_Top,
                    beam_cutouts     = (BeamMode_Top == "beam")
                );
    }
}

// Left: von TL nach BL
module side_left(board_w, board_h) {
    if (BeamMode_Left != "none" && board_h > 1)
    for (j=[0:board_h-2]) {

        side     = "left";
        is_start = (j == 0);              // TL
        is_end   = (j == board_h-2);      // BL

        cfg_start_raw = corner_cfg_for_side(side, true);   // TL
        cfg_end_raw   = corner_cfg_for_side(side, false);  // BL

        // Left ist NICHT Owner → Typ auf "none"
        cfg_start = corner_owner(side,true)
                    ? cfg_start_raw
                    : corner_with_type(cfg_start_raw, "none");

        cfg_end   = corner_owner(side,false)
                    ? cfg_end_raw
                    : corner_with_type(cfg_end_raw, "none");

        pos = [
            -board_w * Tile_Size / 2,
            (j + 1 - board_h/2) * Tile_Size,
            0
        ];

        translate(pos)
            // Orientierung wie im alten openGridbeam (Left)
            zrot(90)
            xrot(180)
            translate([0, -leg_len, 0])
            rotate([0, 90, 0])
                beam_tile(
                    side             = side,
                    is_start         = is_start,
                    is_end           = is_end,
                    corner_start_cfg = cfg_start,
                    corner_end_cfg   = cfg_end,
                    beammode         = BeamMode_Left,
                    beam_cutouts     = (BeamMode_Left == "beam")
                );
    }
}

// Right: von BR nach TR
module side_right(board_w, board_h) {
    if (BeamMode_Right != "none" && board_h > 1)
    for (j = [0 : board_h-2]) {

        side     = "right";
        is_start = (j == 0);              // geometrisch: BR
        is_end   = (j == board_h-2);      // geometrisch: TR

        // Right-Beam ist lokal ebenfalls "umgedreht"
        // → Corner-Konfiguration für Start/End tauschen
        cfg_start_raw = corner_cfg_for_side(side, false); // TR
        cfg_end_raw   = corner_cfg_for_side(side, true);  // BR

        // Right ist NICHT Owner der Corner → Typ immer "none"
        cfg_start = corner_owner(side,true)
                    ? cfg_start_raw
                    : corner_with_type(cfg_start_raw, "none");

        cfg_end   = corner_owner(side,false)
                    ? cfg_end_raw
                    : corner_with_type(cfg_end_raw, "none");

        pos = [
            board_w * Tile_Size / 2,
            (j + 1 - board_h/2) * Tile_Size,
            0
        ];

        translate(pos)
            zrot(-90)
            xrot(180)
            translate([0, -leg_len, 0])
            rotate([0, 90, 0])
                beam_tile(
                    side             = side,
                    is_start         = is_end,
                    is_end           = is_start,
                    corner_start_cfg = cfg_start,
                    corner_end_cfg   = cfg_end,
                    beammode         = BeamMode_Right,
                    beam_cutouts     = (BeamMode_Right == "beam")
                );
    }
}

// ==========================================================
// 10. High-Level: komplettes Board mit Print-Mode (Version B)
// ==========================================================

module openGrid_beam_board(
    board_width  = Board_Width,
    board_height = Board_Height,
    print_mode   = Print_Mode
) {
    if (print_mode) {
        // Bottom + Top zusammen drehen (als ganze Seiten)
        rotate([0,0,90]) {            // oder rotate([90,0,0]) – je nach gewünschter Lage
            side_bottom(board_width, board_height);
            side_top(board_width, board_height);
        }

        // Left + Right unverändert
        side_left(board_width, board_height);
        side_right(board_width, board_height);

    } else {
        side_bottom(board_width, board_height);
        side_top(board_width, board_height);
        side_left(board_width, board_height);
        side_right(board_width, board_height);
    }
}

// ==========================================================
// 11. Test-Module
// ==========================================================

module test_beam_frame() {
    openGrid_beam_board(
        board_width  = Board_Width,
        board_height = Board_Height
    );
}

// Standard-Render

test_beam_frame();

if (Full_or_Lite == "Full") openGridLite(Board_Width=Board_Width, Board_Height=Board_Height, Screw_Mounting="Corners", Chamfers="Corners", Add_Adhesive_Base=false, anchor=BOT, Connector_Holes=true);


//corner_part();
