
include <BOSL2/std.scad>;
use <QuackWorks/openGrid/openGrid.scad>

/*[Board Type]*/
Full_or_Lite = "Lite"; //[Full, Lite, Heavy]
Board_Width = 4;
Board_Height = 8;

// =========================
// OpenGrid Default Parameter
// =========================

/*[OpenGrid - Tile]*/
Tile_Size = 28;
Tile_Thickness = 6.8;
Lite_Tile_Thickness = 4;
Heavy_Tile_Thickness = 13.8;
Heavy_Tile_Gap = 0.2;
Intersection_Distance   = 4.2; // Chamfer-Länge

/*[OpenGrid - Connector]*/
connector_cutout_radius        = 2.6;
connector_cutout_dimple_radius = 2.7;
connector_cutout_separation    = 2.5;
connector_cutout_height        = 2.4;
lite_cutout_distance_from_top  = 1;
         
/*[OpenGrid - border]*/
Connector_Tolerance  = 0.05; // better 0.1?

// =========================
// OpenGrid Beam Parameter
// =========================

/*[OpenGrid - Tile Derived]*/
th = // Kachelstärke kurz, abhängig von Full_or_Lite
    Full_or_Lite == "Lite"  ? Lite_Tile_Thickness :
    Full_or_Lite == "Heavy" ? Heavy_Tile_Thickness :
    Tile_Thickness;
// Diagonal of the grid corner
hypthenuse = sqrt(2*Intersection_Distance*Intersection_Distance);

/*[OpenGrid - Connector Derived]*/
cut_distance_to_top = (th == Lite_Tile_Thickness) 
     ? (lite_cutout_distance_from_top + connector_cutout_height / 2)
     : (th / 2);
// defines the width of the beam: 5.1
connector_length_half   = connector_cutout_radius + connector_cutout_separation; 

/*[Beam Parameters]*/
// defines the width of the beam: 9.1
leg_len = th + connector_length_half;    
// diagonale from Coordinates Center to Beam 
back_offset = th / sqrt(2);
// diagonale vom Beam zu Ende Block wenn Beam cube wäre          
front_offset = connector_length_half / sqrt(2); 
// diameter of the base part
bottom_to_top =  (leg_len *2 / sqrt(2) - back_offset - front_offset);
// lenght of end segment varies if joint or chamfer present
extension    = Tile_Size / 2 - Intersection_Distance; 

// =========================
// Settings/ Options
// =========================

/*[Beam Options]*/
Beam_Segments = false;
Beam_Bottom   = true;
Beam_Left     = true;
Beam_Top      = true;
Beam_Right    = true;
// 0..1: Anteil Segmentlänge pro Ende ohne Joint/Chamfer (default 0.5)
Beam_Extension_Factor = 0.5; 

// l r : perspective left or right of a beam 
// looking to the board over individual beam

/*[Board Connector Options]*/
Boardconnector_cutouts  = true;
Boardconnector_Bottom_l = true;
Boardconnector_Bottom_r = true;
Boardconnector_Left_l    = true;
Boardconnector_Left_r    = true;
Boardconnector_Top_l    = true;
Boardconnector_Top_r    = true;
Boardconnector_Right_l   = true;
Boardconnector_Right_r   = true;

/*[Beam Connector Options]*/
Beamconnector_cutouts   = true;
Beamconnector_Bottom_l  = true;
Beamconnector_Bottom_r  = true;
Beamconnector_Left_l    = true;
Beamconnector_Left_r    = true;
Beamconnector_Top_l     = true;
Beamconnector_Top_r     = true;
Beamconnector_Right_l   = true;
Beamconnector_Right_r   = true;

/*[Joint Options]*/
Joints              = true;
Joint_Bottom_l      = true; // positioned at Joint_Left_r
Joint_Bottom_r      = true; // positioned Joint_Right_l
Joint_Left_l        = false; // positioned at_Top_r 
Joint_Left_r        = false;
Joint_Top_l         = true; // positioned Joint_Right_r
Joint_Top_r         = true;
Joint_Right_l       = false;
Joint_Right_r       = false;

// removes Beamconnectors and Connector at joint.
Joint_attached = true; 

/*[Chamfer Options]*/
Chamfers = false;
Chamfer_Bottom_l     = true;
Chamfer_Bottom_r     = true;
Chamfer_Left_l       = true;
Chamfer_Left_r       = true;
Chamfer_Top_l        = true;
Chamfer_Top_r        = true;
Chamfer_Right_l      = true;
Chamfer_Right_r      = true;

// =========================
// Test Options
// =========================

/*[Joint Mirror Options]*/
Joint_Mirror         = true;
Joint_Mirror_Bottom_l = false;
Joint_Mirror_Bottom_r = false;
Joint_Mirror_Left_l   = false;
Joint_Mirror_Left_r   = false;
Joint_Mirror_Top_l    = false;
Joint_Mirror_Top_r    = false;
Joint_Mirror_Right_l  = false;
Joint_Mirror_Right_r  = false;

/*[Joint Rotation Options]*/
Joint_Rotate       = 0; // degrees
Joint_Rot_Bottom_l = 0; 
Joint_Rot_Bottom_r = 0;
Joint_Rot_Left_l   = 0;
Joint_Rot_Left_r   = 0;
Joint_Rot_Top_l    = 0;
Joint_Rot_Top_r    = 0;
Joint_Rot_Right_l  = 0;
Joint_Rot_Right_r  = 0;

/*[Print Options]*/
// TOGGLE: true = wie im Beam, false = „roh“
use_beam_transform = true; 

// =========================
// Basis-Geometrien 2D
// =========================

module legs_2d() { // L-Profil (zwei Legs)
    union() {
        square([leg_len, th], center=false);  // waagerechtes Leg
        square([th, leg_len], center=false);  // senkrechtes Leg
    }
}

module triangle_blue() { // Großes Dreieck (auf Leg-Mittellinien)
    polygon(points = [
        [th/2,   th/2],
        [th/2,   leg_len],
        [leg_len, th/2]
    ]);
}

module triangle_small() { // Kleines Dreieck (Kantenlänge = th)
    polygon(points = [
        [0,   0],
        [0,   th],
        [th,  0]
    ]);
}

module triangle_fill() { // Lila Dreieck (Offset = th)
    polygon(points = [
        [th,      th     ],
        [leg_len, th     ],
        [th,      leg_len]
    ]);
}

// =========================
// 2D-Grundform für Extrusion
// =========================

module base_body_2d() {
    // L-Profil minus kleines Eckdreieck, plus die beiden Fülldreiecke
    difference() {
        legs_2d();
        triangle_small();
    }
    triangle_blue();
    triangle_fill();
}

// =========================
// 3D-Grundkörper
// =========================

module base_body(h) {
    linear_extrude(height = h)
        base_body_2d();
}

// =========================
// 3D- Corner Joint (Basis)
// =========================

module joint_leg_segment(d, apply_cutout) { 
    should_cut = (Joint_attached && apply_cutout) || (!Joint_attached);

    difference() {      
        
        union() {
            // 1) ursprünglicher Grundkörper
            base_body(d); // d = individuelle Extrusion
            // 2) Verlängerung ds Grundkörpers
            translate([0, 0, -Intersection_Distance]) // Verlängerung nach -Z
                base_body(d);
        }
            
        if (should_cut) cut_out();
    }
}

module cut_out() {
    //cut-outs an den beam-connectoren,1.834 nach innen
    rotate([45,-90,0]) // place at end of a connector in a leg group
        translate([-Intersection_Distance+connector_cutout_radius-Connector_Tolerance,
        0,
        -bottom_to_top])
            connector_cutout_delete_tool(); 
}

module joint_leg_connector(d,e) { //back_offset

    // 1) ursprünglicher Grundkörper
    base_body(d); // d = individuelle Extrusion

    // 2) Verlängerung ds Grundkörpers
    translate([0, 0, -e]) // e = Rückversatz nach -Z
        base_body(d); // f = Verlängerung nach -Z
}

module joint_raw_part() {
    
    xy_center = back_offset*2 + front_offset;
    P_xy      = -unit([1,1,0]) * xy_center;

    // ------------------------------------
    // Bein-Gruppe (2 Legs)
    // ------------------------------------
    module joint_leg_group() {
        union() {
            // first leg, connection to beam
            joint_leg_segment(Intersection_Distance, false);

            // second leg, rotiert + versetzt
            translate(-P_xy + [connector_length_half/2, 0, 0]) {
                yrot(90)
                    translate(P_xy + [
                        -connector_length_half/2 - hypthenuse/sqrt(2),
                        0,
                        hypthenuse/sqrt(2)
                    ])
                    mirror([0,0,1]) // rotate 180° to fit cutout 
                        joint_leg_segment(Intersection_Distance, true);      
            }
        }
    }

    // ------------------------------------
    // Connector-Gruppe (2 Segmente)
    // ------------------------------------
    module connector_group() {
        union() {
            // first connector, connection to first leg. Stretched to fill gap. Main Segment.
            translate(-P_xy + [connector_length_half/2, 0, 0]) {
                rotate(a = 45, v = [0, 1, 0])     // Corrected yrot
                    translate(P_xy + [-connector_length_half/2, 0, 0])
                        joint_leg_connector(hypthenuse * 1.25, hypthenuse * 0.25);
            }

            // chamfer top (end) To be copied segment
            translate(-P_xy + [sqrt(2)*2, sqrt(2)*2,
                               connector_length_half/2 + Intersection_Distance]) {
                // Rotation um v = [1, 1, 0], dann 45° um z
                rotate(a = 90, v = [1, 1, 0])
                    rotate(a = -45, v = [0, 0, 1])
                        translate(P_xy)
                            joint_leg_connector(hypthenuse * 0.75, 0);
            }
        }
    }


    // ------------------------------------
    // Alles zusammen (jeweils mit Spiegelung)
    // ------------------------------------
    
    module mirror_xy() { //Spiegelung an der YZ-Ebene
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
    
    difference() { // cut it flat
        union() {
            joint_raw_part(); // draw the joint, it has some dirty parts
            hull() { // add a triangle and subtract the part to fill, hull the two and add back joint.
                intersection() { 
                joint_raw_part();
                // filler in the middle of the joint
                translate([th + Intersection_Distance/2,
                    th + Intersection_Distance/2,
                    Intersection_Distance/2 + connector_length_half]) {
                        rotate(a = -angle, v = [1, -1, 0]){ // position in angle of joint
                            zrot(-15) {
                                zmove(0.5)
                                    intersection() { // Filler on the bottom, just for design. hand picked values
                                        regular_prism(3, r=th/2+connector_length_half+1, h=7, center = true); // bottom center
                                        zrot(60)
                                            regular_prism(3, r=th/2+connector_length_half+1, h=7, center = true);
                                    }
                                    
                                // sit on top of the bottom prism's face: the top filler.
                                zmove(-leg_len/2)
                                    regular_prism(3, r=leg_len+3.5, h=leg_len/2, center = false);
                            }
                        }
                    }
                }
            }
        }
        // place a cut part to it.
        translate([th + Intersection_Distance/2,
            th + Intersection_Distance/2,
            Intersection_Distance/2 + connector_length_half]) {
                rotate(a = -angle, v = [1, -1, 0]){ // position correctly
                    zmove((-4*(0.6*th/4))-1.4) // -5 is a good value for Lite. for th not 4 using the multiplier. adjust if you want.
                        cylinder(h = 4, r = th*3, center = true); // center hole possible here.
            }
        }
    }
}


// =========================
// 3D- Corner Chamfer (Basis)
// =========================


module chamfers() {

    difference() {
        joint_raw();

        translate([0, -20, Intersection_Distance-Connector_Tolerance])      // z-Beginn
            cube([40, 40, 40], center=false);
 
    // cut-outs to set chamfers next to each other
    /*
    rotate([-45,90,0]) translate([-Intersection_Distance+connector_cutout_radius,0,back_offset+connector_cutout_height+cut_distance_to_top])
     //-back_offset-connector_cutout_height/2-cut_distance_to_top 
      connector_cutout_delete_tool();   
      */
    }
}


// =========================
// Segment (Basis)
// =========================
module segment(Tile_Size, cutouts_enabled = true) {
    // Grundkörper mit Connector‑Cutouts entlang der Segmentachse
    
    if (cutouts_enabled) {
        difference() {
            base_body(Tile_Size);  // voller Körper mit Höhe Tile_Size

            // Cutout in Segmentmitte. Connector_Tolerance/100 just a tiny bit, so the cutout is not exactly on plane            
            translate([cut_distance_to_top, th + connector_length_half/2 + Connector_Tolerance/100, Tile_Size/2])
                rotate([90, 180, 90])
                    connector_cutout_delete_tool();

            // Zweiter Cutout, um die Segmentachse gedreht
            translate([th + connector_length_half/2 + Connector_Tolerance/100, cut_distance_to_top, Tile_Size/2])
                rotate([90, 0, 180])
                    connector_cutout_delete_tool();
        }
    } else {
        base_body(Tile_Size);
    }

    //if (show_chamfers)
    //    beam_chamfer_fill(left = true);
}

module beam_tile(is_start = false, is_end = false,
                 joint_start = false, joint_end = false,
                 joint_mirror_start = false, joint_mirror_end = false,
                 joint_rot_start = 0, joint_rot_end = 0,
                 joint_start_render = true, joint_end_render = true,
                 beam_cutouts = true,
                 boardconnector_start = false,
                 boardconnector_end   = false,
                 chamfer_start = false,
                 chamfer_end   = false,
                 cutout_flip_start = false,
                 cutout_flip_end   = false,
                 render_body = true) {
    // Segment-Länge bleibt unverändert; Anpassung nur an den Endstücken bei Joints
    segment_length = Tile_Size;
    // Basis-Verlängerung außerhalb der eigentlichen Tile-Länge
    extension_base = extension;

    // Lokaler Beam mit Endstücken ohne Cutouts
    module beam_with_endcaps() {
        // Joint-Anker: verschiebt joint_raw so, dass seine Kontaktfläche (z-min) bei z=0 liegt
        joint_contact_z = Tile_Size - Intersection_Distance-Tile_Size;

        module joint_aligned(use_chamfer = false) {
                translate([0, 0, -joint_contact_z])
                    if (use_chamfer)
                        chamfers();
                    else
                        joint_raw();
        }

        // Hilfsmodul für Joint-Ausrichtung:
        //  - end: Grundorientierung (wie bisher), aber auf z=0 geankert
        //  - start: gespiegelt, ebenfalls um z=0 geankert
        module joint_start_mirrored() {
                // optional quer-Spiegelung für Links/Rechts-Tests
                zrot(joint_rot_start)
                    if (joint_mirror_start)
                        mirror([1, 0, 0])
                            mirror([0, 0, 1])
                                joint_aligned(chamfer_start);
                    else
                        mirror([0, 0, 1])
                            joint_aligned(chamfer_start);
        }

        module joint_end_mirrored() {
                zrot(joint_rot_end)
                    if (joint_mirror_end)
                        mirror([1, 0, 0])
                            joint_aligned(chamfer_end);
                    else
                        joint_aligned(chamfer_end);
        }

        // Bei Joint/Chamfer Endstücke verkürzen, sonst volle Segmentlänge außen anstellen
        shorten_start = (joint_start && is_start) || chamfer_start;
        shorten_end   = (joint_end   && is_end)   || chamfer_end;

        // Außenlänge: ohne Joint/Chamfer skalierbar; mit Feature gekürzt
        extension_start = shorten_start
            ? max(extension_base - Intersection_Distance, 0)
            : segment_length * Beam_Extension_Factor;

        extension_end   = shorten_end
            ? max(extension_base - Intersection_Distance, 0)
            : segment_length * Beam_Extension_Factor;

        // Cutouts in den Verlängerungen (Richtung Joint, 90° zu den Beam-Cutouts)

        module extension_with_cutouts(len, face_to_start = true) {
            if (len > 0)
                difference() { // subtract board-connector cutout from the extension
                    base_body(len);

                    cut_z = face_to_start
                        ? (connector_length_half / 2)
                        : (len - connector_length_half / 2);

                    rot_y = face_to_start ? (-90) : (90);


                    // Abstand vom inneren Eckpunkt zur Mitte des Cutouts
                    translate(unit([1,1,0]) *(bottom_to_top) + [0,0, cut_z]) // back flush
                        rotate([0,rot_y,45]) {
                            if (!face_to_start)
                                rotate([0,0,180]); // flip orientation for end-side connectors
                            if (face_to_start ? cutout_flip_start : cutout_flip_end)
                                rotate([0,0,180]); // optional manual flip per end
                                // Connector_Tolerance/100 so its not flush to plane
                            translate([-Connector_Tolerance/100,0,0])
                                connector_cutout_delete_tool();
                        }
                }
        }
        // zentrales Segment mit Cutouts, mittig um Z=0
        if (render_body && beam_cutouts)
            down(segment_length / 2)
                segment(segment_length, cutouts_enabled = true);
        else if (render_body)
            down(segment_length / 2)
                segment(segment_length, cutouts_enabled = false);

        // Endstück am Anfang (negative Z-Richtung), ohne Cutouts
        if (render_body && is_start)
            translate([0, 0, -segment_length / 2 - extension_start]) {
                if (boardconnector_start)
                    extension_with_cutouts(extension_start, face_to_start = true);
                else
                    base_body(extension_start);
            }

        // Joints werden, falls aktiviert, an beide Enden gesetzt und schließen direkt an die verkürzten Endstücke an.
        render_joint_start = (joint_start && is_start && joint_start_render);
        render_joint_end   = (joint_end   && is_end   && joint_end_render);

        // Joint/Chamfer am Anfang, direkt hinter der (verkürzten) Extension
        if (render_joint_start || (chamfer_start && is_start))
            translate([0, 0, -segment_length / 2 - extension_start])
                joint_start_mirrored();

        // Joint am Ende, direkt hinter der (verkürzten) Extension
        if (render_joint_end || (chamfer_end && is_end))
            translate([0, 0,  segment_length / 2 + extension_end])
                joint_end_mirrored();

        // Endstück am Ende (positive Z-Richtung), ohne Cutouts
        if (render_body && is_end)
            translate([0, 0,  segment_length / 2]) {
                if (boardconnector_end)
                    extension_with_cutouts(extension_end, face_to_start = false);
                else
                    base_body(extension_end);
            }
    }

    // Beam‑Darstellung: entweder „roh“ oder wie im ursprünglichen Beam‑View
    if (use_beam_transform) {
        xrot(180)
        translate([0, -leg_len, 0])
        rotate([0, 90, 0])
            beam_with_endcaps();
    } else {
        beam_with_endcaps();
    }

}

// =========================
// Szene-Gesamtobjekt
// =========================
module scene_all() {
    segment(Tile_Size);
}

// =========================
// Darstellung mit Toggle
// =========================

if (Board_Width == 1 && Board_Height == 1) { // catch 1 by 1 tile: build your "stick"
    if (use_beam_transform) {
        zrot(90)
        translate([0, seg_len/2, -back_offset])
        rotate([90, -45, 0])
            scene_all();
    } else {
        scene_all();
    }      
}


// =============================
// Cutout-Tool aus openGrid
// =============================
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

// Bündelt die Segment-Generierung pro Seite in Options-Reihenfolge (Bottom, Left, Top, Right)
module beam_segments(
    board_w, board_h, tileSize,
    // bottom
    draw_beam_bottom, joint_bottom_on, joint_bottom_start, joint_bottom_end,
    mirror_bottom_start, mirror_bottom_end,
    render_br_bottom, render_bl_bottom,
    beam_cutouts_bottom, board_bottom_start, board_bottom_end,
    chamfer_bottom_start, chamfer_bottom_end,
    rot_bottom_start, rot_bottom_end,
    // left
    draw_beam_left, joint_left_on, joint_left_start, joint_left_end,
    mirror_left_start, mirror_left_end,
    render_tl_left, render_bl_left,
    beam_cutouts_left, board_left_start, board_left_end,
    chamfer_left_start, chamfer_left_end,
    rot_left_start, rot_left_end,
    // top
    draw_beam_top, joint_top_on, joint_top_start, joint_top_end,
    mirror_top_start, mirror_top_end,
    render_tr_top, render_tl_top,
    beam_cutouts_top, board_top_start, board_top_end,
    chamfer_top_start, chamfer_top_end,
    rot_top_start, rot_top_end,
    // right
    draw_beam_right, joint_right_on, joint_right_start, joint_right_end,
    mirror_right_start, mirror_right_end,
    render_tr_right, render_br_right,
    beam_cutouts_right, board_right_start, board_right_end,
    chamfer_right_start, chamfer_right_end,
    rot_right_start, rot_right_end
) {
    // Bottom side (Beam von links nach rechts)
    if (board_w > 1 && (draw_beam_bottom || joint_bottom_on))
        for (i = [0 : board_w - 2])
            translate([(i + 1 - board_w / 2) * tileSize,
                       -board_h * tileSize / 2,
                       0])
                zrot(180)
                    beam_tile(
                        // für die Bottom-Seite Start/Ende gespiegelt,
                        // damit die Verlängerung nach außen zeigt wie bei den anderen Seiten
                        is_start     = (board_w > 1 && i == board_w - 2),
                        is_end       = (board_w > 1 && i == 0),
                        joint_start  = joint_bottom_start,
                        joint_end    = joint_bottom_end,
                        joint_mirror_start = mirror_bottom_start,
                        joint_mirror_end   = mirror_bottom_end,
                        joint_start_render = render_br_bottom,
                        joint_end_render   = render_bl_bottom,
                        joint_rot_start = rot_bottom_start,
                        joint_rot_end   = rot_bottom_end,
                        beam_cutouts = beam_cutouts_bottom,
                        boardconnector_start = board_bottom_start,
                        boardconnector_end   = board_bottom_end,
                        chamfer_start = ((board_w > 1 && i == board_w - 2) ? chamfer_bottom_start : false),
                        chamfer_end   = ((board_w > 1 && i == 0) ? chamfer_bottom_end : false),
                        cutout_flip_start = true,
                        cutout_flip_end   = false,
                        render_body = draw_beam_bottom
                    );

    // Left side (Beam von oben nach unten)
    if (board_h > 1 && (draw_beam_left || joint_left_on))
        for (j = [0 : board_h - 2])
            translate([-board_w * tileSize / 2,
                       (j + 1 - board_h / 2) * tileSize,
                       0])
                zrot(90)
                    beam_tile(
                        // Start = Top/start? (j==0 war ursprüngliche Start=oben, Ende=unten)
                        is_start     = (board_h > 1 && j == 0),
                        is_end       = (board_h > 1 && j == board_h - 2),
                        joint_start  = joint_left_start,
                        joint_end    = joint_left_end,
                        joint_mirror_start = mirror_left_start,
                        joint_mirror_end   = mirror_left_end,
                        joint_start_render = render_tl_left,
                        joint_end_render   = render_bl_left,
                        joint_rot_start = rot_left_start,
                        joint_rot_end   = rot_left_end,
                        beam_cutouts = beam_cutouts_left,
                        boardconnector_start = board_left_start,
                        boardconnector_end   = board_left_end,
                        chamfer_start = ((board_h > 1 && j == 0) ? chamfer_left_start : false),
                        chamfer_end   = ((board_h > 1 && j == board_h - 2) ? chamfer_left_end : false),
                        render_body = draw_beam_left
                    );

    // Top side (Beam von links nach rechts)
    if (board_w > 1 && (draw_beam_top || joint_top_on))
        for (i = [0 : board_w - 2])
            translate([(i + 1 - board_w / 2) * tileSize,
                       board_h * tileSize / 2,
                       0])
                beam_tile(
                    is_start     = (board_w > 1 && i == 0),
                    is_end       = (board_w > 1 && i == board_w - 2),
                    joint_start  = joint_top_start,
                    joint_end    = joint_top_end,
                    joint_mirror_start = mirror_top_start,
                    joint_mirror_end   = mirror_top_end,
                    joint_start_render = render_tr_top,
                    joint_end_render   = render_tl_top,
                    joint_rot_start = rot_top_start,
                    joint_rot_end   = rot_top_end,
                    beam_cutouts = beam_cutouts_top,
                    boardconnector_start = board_top_start,
                    boardconnector_end   = board_top_end,
                    chamfer_start = ((board_w > 1 && i == 0) ? chamfer_top_start : false),
                    chamfer_end   = ((board_w > 1 && i == board_w - 2) ? chamfer_top_end : false),
                    render_body = draw_beam_top
                );

    // Right side (Beam von unten nach oben – Start/Ende gespiegelt)
    if (board_h > 1 && (draw_beam_right || joint_right_on))
        for (j = [0 : board_h - 2])
            translate([board_w * tileSize / 2,
                       (j + 1 - board_h / 2) * tileSize,
                       0])
                zrot(-90)
                    beam_tile(
                        // für die rechte Seite Start/Ende gespiegelt,
                        // damit die Verlängerung nach außen zeigt wie bei den anderen Seiten
                        is_start     = (board_h > 1 && j == board_h - 2),
                        is_end       = (board_h > 1 && j == 0),
                        joint_start  = joint_right_start,
                        joint_end    = joint_right_end,
                        // Start = Top‑Right, End = Bottom‑Right
                        joint_mirror_start = mirror_right_start,
                        joint_mirror_end   = mirror_right_end,
                        joint_start_render = render_tr_right,
                        joint_end_render   = render_br_right,
                        joint_rot_start = rot_right_start,
                        joint_rot_end   = rot_right_end,
                        beam_cutouts = beam_cutouts_right,
                        boardconnector_start = board_right_start,
                        boardconnector_end   = board_right_end,
                        chamfer_start = ((board_h > 1 && j == board_h - 2) ? chamfer_right_start : false),
                        chamfer_end   = ((board_h > 1 && j == 0) ? chamfer_right_end : false),
                        render_body = draw_beam_right
                    );
}
//END CUTOUT TOOL


// =========================
// Szene mit openGrid‑Interface
// =========================
module scene(Board_Width, Board_Height, tileSize = Tile_Size, Tile_Thickness = Tile_Thickness, anchor = CENTER, spin = 0, orient = UP) {
    // effektive Dicke ist th (abhängig von Full_or_Lite)
    effective_thickness = th;

    attachable(anchor, spin, orient, size = [Board_Width * tileSize, Board_Height * tileSize, effective_thickness]) {
        render(convexity = 2) {
            // derived toggles for connectors per side/end
            // board connectors: zentrale Cutouts im Segment
            beam_cutouts_bottom = Boardconnector_cutouts && (Boardconnector_Bottom_l || Boardconnector_Bottom_r);
            beam_cutouts_top    = Boardconnector_cutouts && (Boardconnector_Top_l    || Boardconnector_Top_r);
            beam_cutouts_left   = Boardconnector_cutouts && (Boardconnector_Left_r   || Boardconnector_Left_l);
            beam_cutouts_right  = Boardconnector_cutouts && (Boardconnector_Right_r  || Boardconnector_Right_l);

            // Beam-Connector Optionen (per End) – Joint_attached schaltet nur die betroffenen Ecken später aus
            beamconnector_allowed = Beamconnector_cutouts;

            // beam connectors: End-Cutouts in den Verlängerungen
            board_bottom_start = beamconnector_allowed && Beamconnector_Bottom_r && !(Joint_attached && Joint_Bottom_r);
            board_bottom_end   = beamconnector_allowed && Beamconnector_Bottom_l && !(Joint_attached && Joint_Bottom_l);

            board_top_start = beamconnector_allowed && Beamconnector_Top_l && !(Joint_attached && Joint_Top_r);
            board_top_end   = beamconnector_allowed && Beamconnector_Top_r && !(Joint_attached && Joint_Top_l);

            // Left beam: läuft von oben (start) nach unten (end)
            board_left_start = beamconnector_allowed && Beamconnector_Left_r && !(Joint_attached && Joint_Left_r); // r = top/start
            board_left_end   = beamconnector_allowed && Beamconnector_Left_l && !(Joint_attached && Joint_Left_l); // l = bottom/end

            // Right beam: läuft von unten (start) nach oben (end)
            board_right_start = beamconnector_allowed && Beamconnector_Right_l && !(Joint_attached && Joint_Right_r); // l = bottom/start
            board_right_end   = beamconnector_allowed && Beamconnector_Right_r && !(Joint_attached && Joint_Right_l); // r = top/end

            // Corner-Aliase laut Kommentaren (gleiche Ecke, unterschiedliche Perspektive)
            corner_bottom_l = Joint_Bottom_l || Joint_Left_r;   // Bottom links = Left rechts
            corner_bottom_r = Joint_Bottom_r || Joint_Right_l;  // Bottom rechts = Right links
            corner_top_l    = Joint_Top_l    || Joint_Right_r;  // Top links    = Right rechts
            corner_top_r    = Joint_Top_r    || Joint_Left_l;   // Top rechts   = Left links

            // joint toggles per side (Aliase erlauben Kürzung, Render-Owner separat gesteuert)
            joint_bottom_start = Joints && corner_bottom_r; // Start = rechts
            joint_bottom_end   = Joints && corner_bottom_l; // Ende  = links
            // Top-Beam: r/l stehen für rechts/links am Beam, getauscht
            joint_top_start    = Joints && corner_top_r;    // Start = rechts
            joint_top_end      = Joints && corner_top_l;    // Ende  = links
            // Left‑Side Beam: r/l stehen für rechts/links am Beam
            joint_left_start   = Joints && corner_top_r;    // top/start (alias Left_r / Bottom_l)
            joint_left_end     = Joints && corner_bottom_l; // bottom/end (alias Left_l / Top_r)
            // Right‑Side Beam: r/l stehen für rechts/links am Beam
            joint_right_start  = Joints && corner_top_l;    // bottom/start (Right_r / Top_l)
            joint_right_end    = Joints && corner_bottom_r; // top/end   (Right_l / Bottom_r)

            joint_bottom_on = joint_bottom_start || joint_bottom_end;
            joint_top_on    = joint_top_start    || joint_top_end;
            joint_left_on   = joint_left_start   || joint_left_end;
            joint_right_on  = joint_right_start  || joint_right_end;

            // Mirror/Rotation pro Joint, plus globale Overrides
            mirror_bottom_start = Joint_Mirror || Joint_Mirror_Bottom_r;
            mirror_bottom_end   = Joint_Mirror || Joint_Mirror_Bottom_l;
            mirror_top_start    = Joint_Mirror || Joint_Mirror_Top_r;
            mirror_top_end      = Joint_Mirror || Joint_Mirror_Top_l;
            mirror_left_start   = Joint_Mirror || Joint_Mirror_Left_r;
            mirror_left_end     = Joint_Mirror || Joint_Mirror_Left_l;
            mirror_right_start  = Joint_Mirror || Joint_Mirror_Right_r;
            mirror_right_end    = Joint_Mirror || Joint_Mirror_Right_l;

            rot_bottom_start = Joint_Rotate + Joint_Rot_Bottom_r;
            rot_bottom_end   = Joint_Rotate + Joint_Rot_Bottom_l;
            rot_top_start    = Joint_Rotate + Joint_Rot_Top_r;
            rot_top_end      = Joint_Rotate + Joint_Rot_Top_l;
            rot_left_start   = Joint_Rotate + Joint_Rot_Left_r;
            rot_left_end     = Joint_Rotate + Joint_Rot_Left_l;
            rot_right_start  = Joint_Rotate + Joint_Rot_Right_r;
            rot_right_end    = Joint_Rotate + Joint_Rot_Right_l;

            // Render-Zuordnung pro Ecke (ein Owner), falls ein Beam ausgeschaltet ist, springt der Nachbar ein
            // global Beam_Segments als Override nur für sichtbare Beams
            // Joints/Chamfers/Owner-Zuweisung basieren weiter auf den Einzel-Flags
            beam_bottom_enabled = Beam_Segments || Beam_Bottom;
            beam_top_enabled    = Beam_Segments || Beam_Top;
            beam_left_enabled   = Beam_Segments || Beam_Left;
            beam_right_enabled  = Beam_Segments || Beam_Right;

            draw_beam_bottom = beam_bottom_enabled;
            draw_beam_top    = beam_top_enabled;
            draw_beam_left   = beam_left_enabled;
            draw_beam_right  = beam_right_enabled;

            // Corner Ownership: Beams mit Joint an der Ecke haben Vorrang; sonst Beam-Sichtbarkeit
            bottom_joint_on = Joint_Bottom_l || Joint_Bottom_r;
            top_joint_on    = Joint_Top_l    || Joint_Top_r;

            render_corner_bl_on_bottom = bottom_joint_on || (Beam_Bottom && !joint_left_on);
            render_corner_bl_on_left   = !render_corner_bl_on_bottom && (Beam_Left || joint_left_on);

            render_corner_br_on_bottom = bottom_joint_on || (Beam_Bottom && !joint_right_on);
            render_corner_br_on_right  = !render_corner_br_on_bottom && (Beam_Right || joint_right_on);

            render_corner_tl_on_top  = top_joint_on || (Beam_Top && !joint_left_on);
            render_corner_tl_on_left = !render_corner_tl_on_top && (Beam_Left || joint_left_on);
            render_corner_tl_on_right = !render_corner_tl_on_top && !render_corner_tl_on_left && (Beam_Right || joint_right_on);

            render_corner_tr_on_top   = top_joint_on || (Beam_Top && !joint_right_on);
            render_corner_tr_on_right = !render_corner_tr_on_top && (Beam_Right || joint_right_on);
            render_corner_tr_on_left  = !render_corner_tr_on_top && !render_corner_tr_on_right && (Beam_Left || joint_left_on);

            chamfer_bottom_start = Chamfers && Chamfer_Bottom_r;
            chamfer_bottom_end   = Chamfers && Chamfer_Bottom_l;
            // Top-Seite: l/r tauschen (r = links/Start, l = rechts/Ende)
            chamfer_top_start    = Chamfers && Chamfer_Top_r;
            chamfer_top_end      = Chamfers && Chamfer_Top_l;
            // Chamfer Right bleibt getauscht, Chamfer Left zurück auf ursprüngliche Zuordnung
            chamfer_left_start   = Chamfers && Chamfer_Left_r; // top/start
            chamfer_left_end     = Chamfers && Chamfer_Left_l; // bottom/end
            chamfer_right_start  = Chamfers && Chamfer_Right_r; // bottom/start
            chamfer_right_end    = Chamfers && Chamfer_Right_l; // top/end

            // Segmente an den Positionen der openGrid‑Connector Holes platzieren
            // Joints können auch ohne sichtbare Beams angezeigt werden.
            beam_segments(
                Board_Width, Board_Height, tileSize,
                // bottom
                draw_beam_bottom, joint_bottom_on, joint_bottom_start, joint_bottom_end,
                mirror_bottom_start, mirror_bottom_end,
                render_corner_br_on_bottom, render_corner_bl_on_bottom,
                beam_cutouts_bottom, board_bottom_start, board_bottom_end,
                chamfer_bottom_start, chamfer_bottom_end,
                rot_bottom_start, rot_bottom_end,
                // left
                draw_beam_left, joint_left_on, joint_left_start, joint_left_end,
                mirror_left_start, mirror_left_end,
                render_corner_tl_on_left, render_corner_bl_on_left,
                beam_cutouts_left, board_left_start, board_left_end,
                chamfer_left_start, chamfer_left_end,
                rot_left_start, rot_left_end,
                // top
                draw_beam_top, joint_top_on, joint_top_start, joint_top_end,
                mirror_top_start, mirror_top_end,
                render_corner_tr_on_top, render_corner_tl_on_top,
                beam_cutouts_top, board_top_start, board_top_end,
                chamfer_top_start, chamfer_top_end,
                rot_top_start, rot_top_end,
                // right
                draw_beam_right, joint_right_on, joint_right_start, joint_right_end,
                mirror_right_start, mirror_right_end,
                render_corner_tr_on_right, render_corner_br_on_right,
                beam_cutouts_right, board_right_start, board_right_end,
                chamfer_right_start, chamfer_right_end,
                rot_right_start, rot_right_end
            );
        }
        children();
    }
}

/* ========== Render ========== */
//base_body_2d();
//color("turquoise") base_body(1);
scene(Board_Width=Board_Width, Board_Height=Board_Height);

