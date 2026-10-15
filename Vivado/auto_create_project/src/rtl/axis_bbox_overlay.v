`timescale 1ns / 1ps

// AXI4-Stream RGB888 overlay for up to three faces.
// cfg_x: enable[31], x_max[27:16], x_min[11:0].
// cfg_y: distance_dm[7:4] in [31:28], y_max[27:16],
//        distance_dm[3:0] in [15:12], y_min[11:0].
module axis_bbox_overlay #(
    parameter [23:0] BOX_COLOR = 24'h00FF00,
    parameter [23:0] LABEL_BACKGROUND = 24'h000000,
    parameter integer BOX_THICKNESS = 4,
    parameter integer FRAME_WIDTH = 1280
) (
    (* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 ACLK CLK" *)
    (* X_INTERFACE_PARAMETER = "XIL_INTERFACENAME ACLK, ASSOCIATED_BUSIF S_AXIS_VIDEO:M_AXIS_VIDEO, ASSOCIATED_RESET aresetn, FREQ_HZ 125000000" *)
    input wire aclk,
    (* X_INTERFACE_INFO = "xilinx.com:signal:reset:1.0 ARESETN RST" *)
    (* X_INTERFACE_PARAMETER = "XIL_INTERFACENAME ARESETN, POLARITY ACTIVE_LOW" *)
    input wire aresetn,
    input wire [31:0] cfg_x0, input wire [31:0] cfg_y0,
    input wire [31:0] cfg_x1, input wire [31:0] cfg_y1,
    input wire [31:0] cfg_x2, input wire [31:0] cfg_y2,

    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 S_AXIS_VIDEO TDATA" *)
    (* X_INTERFACE_PARAMETER = "XIL_INTERFACENAME S_AXIS_VIDEO, TDATA_NUM_BYTES 3, TUSER_WIDTH 1, HAS_TREADY 1, HAS_TKEEP 1, HAS_TLAST 1" *)
    input wire [23:0] s_axis_video_tdata,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 S_AXIS_VIDEO TKEEP" *) input wire [2:0] s_axis_video_tkeep,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 S_AXIS_VIDEO TLAST" *) input wire s_axis_video_tlast,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 S_AXIS_VIDEO TUSER" *) input wire s_axis_video_tuser,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 S_AXIS_VIDEO TVALID" *) input wire s_axis_video_tvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 S_AXIS_VIDEO TREADY" *) output wire s_axis_video_tready,

    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 M_AXIS_VIDEO TDATA" *)
    (* X_INTERFACE_PARAMETER = "XIL_INTERFACENAME M_AXIS_VIDEO, TDATA_NUM_BYTES 3, TUSER_WIDTH 1, HAS_TREADY 1, HAS_TKEEP 1, HAS_TLAST 1" *)
    output wire [23:0] m_axis_video_tdata,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 M_AXIS_VIDEO TKEEP" *) output wire [2:0] m_axis_video_tkeep,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 M_AXIS_VIDEO TLAST" *) output wire m_axis_video_tlast,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 M_AXIS_VIDEO TUSER" *) output wire m_axis_video_tuser,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 M_AXIS_VIDEO TVALID" *) output wire m_axis_video_tvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 M_AXIS_VIDEO TREADY" *) input wire m_axis_video_tready
);
    localparam integer FONT_SCALE=2, CHAR_PITCH=12, LABEL_CHARS=11;
    localparam integer LABEL_WIDTH=CHAR_PITCH*LABEL_CHARS, LABEL_HEIGHT=16;

    (* ASYNC_REG = "TRUE" *) reg [31:0] cfg_x0_meta, cfg_x0_sync, cfg_y0_meta, cfg_y0_sync;
    (* ASYNC_REG = "TRUE" *) reg [31:0] cfg_x1_meta, cfg_x1_sync, cfg_y1_meta, cfg_y1_sync;
    (* ASYNC_REG = "TRUE" *) reg [31:0] cfg_x2_meta, cfg_x2_sync, cfg_y2_meta, cfg_y2_sync;
    reg [31:0] cfg_x0_active, cfg_y0_active, cfg_x1_active, cfg_y1_active;
    reg [31:0] cfg_x2_active, cfg_y2_active;
    reg [11:0] pixel_x, pixel_y;

    // Three-stage elastic pipeline.  The whole pipeline stalls together when
    // the downstream AXI4-Stream interface applies backpressure.
    reg valid0, valid1, valid2;
    reg [23:0] data0, data1, data2;
    reg [2:0] keep0, keep1, keep2;
    reg last0, last1, last2, user0, user1, user2;
    reg [11:0] px0, py0;
    reg [31:0] sx0, sy0, sx1, sy1, sx2, sy2;
    reg draw_box1, draw_bg1;
    reg [14:0] glyph0_1, glyph1_1, glyph2_1;

    wire pipeline_enable = !valid2 || m_axis_video_tready;
    wire input_transfer = s_axis_video_tvalid && s_axis_video_tready;

    function [4:0] glyph_row;
        input [7:0] c; input [2:0] r;
        begin
            glyph_row=0;
            case(c)
                "P":case(r) 0:glyph_row=5'b11110;1:glyph_row=5'b10001;2:glyph_row=5'b10001;3:glyph_row=5'b11110;4:glyph_row=5'b10000;5:glyph_row=5'b10000;6:glyph_row=5'b10000;endcase
                "E":case(r) 0:glyph_row=5'b11111;1:glyph_row=5'b10000;2:glyph_row=5'b10000;3:glyph_row=5'b11110;4:glyph_row=5'b10000;5:glyph_row=5'b10000;6:glyph_row=5'b11111;endcase
                "O":case(r) 0:glyph_row=5'b01110;1:glyph_row=5'b10001;2:glyph_row=5'b10001;3:glyph_row=5'b10001;4:glyph_row=5'b10001;5:glyph_row=5'b10001;6:glyph_row=5'b01110;endcase
                "L":case(r) 0:glyph_row=5'b10000;1:glyph_row=5'b10000;2:glyph_row=5'b10000;3:glyph_row=5'b10000;4:glyph_row=5'b10000;5:glyph_row=5'b10000;6:glyph_row=5'b11111;endcase
                "M":case(r) 0:glyph_row=5'b10001;1:glyph_row=5'b11011;2:glyph_row=5'b10101;3:glyph_row=5'b10101;4:glyph_row=5'b10001;5:glyph_row=5'b10001;6:glyph_row=5'b10001;endcase
                "0":case(r) 0:glyph_row=5'b01110;1:glyph_row=5'b10001;2:glyph_row=5'b10011;3:glyph_row=5'b10101;4:glyph_row=5'b11001;5:glyph_row=5'b10001;6:glyph_row=5'b01110;endcase
                "1":case(r) 0:glyph_row=5'b00100;1:glyph_row=5'b01100;2:glyph_row=5'b00100;3:glyph_row=5'b00100;4:glyph_row=5'b00100;5:glyph_row=5'b00100;6:glyph_row=5'b01110;endcase
                "2":case(r) 0:glyph_row=5'b01110;1:glyph_row=5'b10001;2:glyph_row=5'b00001;3:glyph_row=5'b00010;4:glyph_row=5'b00100;5:glyph_row=5'b01000;6:glyph_row=5'b11111;endcase
                "3":case(r) 0:glyph_row=5'b11110;1:glyph_row=5'b00001;2:glyph_row=5'b00001;3:glyph_row=5'b01110;4:glyph_row=5'b00001;5:glyph_row=5'b00001;6:glyph_row=5'b11110;endcase
                "4":case(r) 0:glyph_row=5'b00010;1:glyph_row=5'b00110;2:glyph_row=5'b01010;3:glyph_row=5'b10010;4:glyph_row=5'b11111;5:glyph_row=5'b00010;6:glyph_row=5'b00010;endcase
                "5":case(r) 0:glyph_row=5'b11111;1:glyph_row=5'b10000;2:glyph_row=5'b10000;3:glyph_row=5'b11110;4:glyph_row=5'b00001;5:glyph_row=5'b00001;6:glyph_row=5'b11110;endcase
                "6":case(r) 0:glyph_row=5'b01110;1:glyph_row=5'b10000;2:glyph_row=5'b10000;3:glyph_row=5'b11110;4:glyph_row=5'b10001;5:glyph_row=5'b10001;6:glyph_row=5'b01110;endcase
                "7":case(r) 0:glyph_row=5'b11111;1:glyph_row=5'b00001;2:glyph_row=5'b00010;3:glyph_row=5'b00100;4:glyph_row=5'b01000;5:glyph_row=5'b01000;6:glyph_row=5'b01000;endcase
                "8":case(r) 0:glyph_row=5'b01110;1:glyph_row=5'b10001;2:glyph_row=5'b10001;3:glyph_row=5'b01110;4:glyph_row=5'b10001;5:glyph_row=5'b10001;6:glyph_row=5'b01110;endcase
                "9":case(r) 0:glyph_row=5'b01110;1:glyph_row=5'b10001;2:glyph_row=5'b10001;3:glyph_row=5'b01111;4:glyph_row=5'b00001;5:glyph_row=5'b00001;6:glyph_row=5'b01110;endcase
                ".":case(r) 5:glyph_row=5'b00110;6:glyph_row=5'b00110;endcase
                default:glyph_row=0;
            endcase
        end
    endfunction

    function box_edge;
        input [11:0] px,py; input [31:0] cx,cy;
        reg [11:0] xmin,xmax,ymin,ymax; reg ix,iy;
        begin
            xmin=cx[11:0];xmax=cx[27:16];ymin=cy[11:0];ymax=cy[27:16];
            ix=(px>=xmin)&&(px<=xmax);iy=(py>=ymin)&&(py<=ymax);
            box_edge=cx[31]&&(xmin<=xmax)&&(ymin<=ymax)&&
                ((ix&&py>=ymin&&py<ymin+BOX_THICKNESS)||
                 (ix&&py<=ymax&&py+BOX_THICKNESS>ymax)||
                 (iy&&px>=xmin&&px<xmin+BOX_THICKNESS)||
                 (iy&&px<=xmax&&px+BOX_THICKNESS>xmax));
        end
    endfunction

    function label_background_pixel;
        input [11:0] px,py; input [31:0] cx,cy;
        reg [11:0] lx,ly;
        begin
            lx=cx[11:0]>FRAME_WIDTH-LABEL_WIDTH ? FRAME_WIDTH-LABEL_WIDTH:cx[11:0];
            ly=cy[11:0]>LABEL_HEIGHT+2 ? cy[11:0]-LABEL_HEIGHT-2:cy[11:0]+BOX_THICKNESS+2;
            label_background_pixel=cx[31]&&px>=lx&&px<lx+LABEL_WIDTH&&py>=ly&&py<ly+LABEL_HEIGHT;
        end
    endfunction

    // Packed result: valid, ASCII character, font row, font column.
    // Distance digits arrive from software already encoded as decimal BCD in
    // cfg_y[31:28] and cfg_y[15:12], avoiding a divider in the pixel path.
    function [14:0] label_meta;
        input [11:0] px,py; input [31:0] cx,cy;
        reg [11:0] lx,ly,dx,dy;
        reg [7:0] ch;
        reg [3:0] ci,cp;
        reg [2:0] fr,fc;
        begin
            label_meta=0;
            lx=cx[11:0]>FRAME_WIDTH-LABEL_WIDTH ? FRAME_WIDTH-LABEL_WIDTH:cx[11:0];
            ly=cy[11:0]>LABEL_HEIGHT+2 ? cy[11:0]-LABEL_HEIGHT-2:cy[11:0]+BOX_THICKNESS+2;
            if(cx[31]&&px>=lx&&px<lx+LABEL_WIDTH&&py>ly&&py<ly+15)begin
                dx=px-lx;
                dy=py-ly-1;
                if(dx<12)begin ci=0;cp=dx;end
                else if(dx<24)begin ci=1;cp=dx-12;end
                else if(dx<36)begin ci=2;cp=dx-24;end
                else if(dx<48)begin ci=3;cp=dx-36;end
                else if(dx<60)begin ci=4;cp=dx-48;end
                else if(dx<72)begin ci=5;cp=dx-60;end
                else if(dx<84)begin ci=6;cp=dx-72;end
                else if(dx<96)begin ci=7;cp=dx-84;end
                else if(dx<108)begin ci=8;cp=dx-96;end
                else if(dx<120)begin ci=9;cp=dx-108;end
                else begin ci=10;cp=dx-120;end
                fr=dy[3:1];
                fc=cp[3:1];
                ch=" ";
                case(ci)
                    0:ch="P";1:ch="E";2:ch="O";3:ch="P";4:ch="L";5:ch="E";
                    6:ch=" ";7:ch="0"+cy[31:28];8:ch=".";
                    9:ch="0"+cy[15:12];10:ch="M";
                    default:ch=" ";
                endcase
                if(fr<7&&fc<5)label_meta={1'b1,ch,fr,fc};
            end
        end
    endfunction

    wire calc_box=box_edge(px0,py0,sx0,sy0)||box_edge(px0,py0,sx1,sy1)||box_edge(px0,py0,sx2,sy2);
    wire calc_bg=label_background_pixel(px0,py0,sx0,sy0)||label_background_pixel(px0,py0,sx1,sy1)||label_background_pixel(px0,py0,sx2,sy2);
    wire [14:0] calc_glyph0=label_meta(px0,py0,sx0,sy0);
    wire [14:0] calc_glyph1=label_meta(px0,py0,sx1,sy1);
    wire [14:0] calc_glyph2=label_meta(px0,py0,sx2,sy2);
    wire [4:0] glyph_bits0=glyph_row(glyph0_1[13:6],glyph0_1[5:3]);
    wire [4:0] glyph_bits1=glyph_row(glyph1_1[13:6],glyph1_1[5:3]);
    wire [4:0] glyph_bits2=glyph_row(glyph2_1[13:6],glyph2_1[5:3]);
    wire glyph_on0=glyph0_1[14]&&glyph_bits0[4-glyph0_1[2:0]];
    wire glyph_on1=glyph1_1[14]&&glyph_bits1[4-glyph1_1[2:0]];
    wire glyph_on2=glyph2_1[14]&&glyph_bits2[4-glyph2_1[2:0]];
    wire draw_text2=glyph_on0||glyph_on1||glyph_on2;

    assign s_axis_video_tready=pipeline_enable;
    assign m_axis_video_tvalid=valid2;
    assign m_axis_video_tdata=data2;
    assign m_axis_video_tkeep=keep2;
    assign m_axis_video_tlast=last2;
    assign m_axis_video_tuser=user2;

    always @(posedge aclk) begin
        if(!aresetn)begin
            cfg_x0_meta<=0;cfg_x0_sync<=0;cfg_y0_meta<=0;cfg_y0_sync<=0;
            cfg_x1_meta<=0;cfg_x1_sync<=0;cfg_y1_meta<=0;cfg_y1_sync<=0;
            cfg_x2_meta<=0;cfg_x2_sync<=0;cfg_y2_meta<=0;cfg_y2_sync<=0;
            cfg_x0_active<=0;cfg_y0_active<=0;cfg_x1_active<=0;cfg_y1_active<=0;cfg_x2_active<=0;cfg_y2_active<=0;
        end else begin
            cfg_x0_meta<=cfg_x0;cfg_x0_sync<=cfg_x0_meta;cfg_y0_meta<=cfg_y0;cfg_y0_sync<=cfg_y0_meta;
            cfg_x1_meta<=cfg_x1;cfg_x1_sync<=cfg_x1_meta;cfg_y1_meta<=cfg_y1;cfg_y1_sync<=cfg_y1_meta;
            cfg_x2_meta<=cfg_x2;cfg_x2_sync<=cfg_x2_meta;cfg_y2_meta<=cfg_y2;cfg_y2_sync<=cfg_y2_meta;
            if(input_transfer&&s_axis_video_tuser)begin
                cfg_x0_active<=cfg_x0_sync;cfg_y0_active<=cfg_y0_sync;
                cfg_x1_active<=cfg_x1_sync;cfg_y1_active<=cfg_y1_sync;
                cfg_x2_active<=cfg_x2_sync;cfg_y2_active<=cfg_y2_sync;
            end
        end
    end

    always @(posedge aclk) begin
        if(!aresetn)begin pixel_x<=0;pixel_y<=0;end
        else if(input_transfer)begin
            if(s_axis_video_tuser)begin pixel_y<=s_axis_video_tlast?1:0;pixel_x<=s_axis_video_tlast?0:1;end
            else if(s_axis_video_tlast)begin pixel_x<=0;pixel_y<=pixel_y+1;end
            else pixel_x<=pixel_x+1;
        end
    end

    always @(posedge aclk) begin
        if(!aresetn)begin
            valid0<=0;valid1<=0;valid2<=0;
            data0<=0;data1<=0;data2<=0;
            keep0<=0;keep1<=0;keep2<=0;
            last0<=0;last1<=0;last2<=0;
            user0<=0;user1<=0;user2<=0;
            px0<=0;py0<=0;
            sx0<=0;sy0<=0;sx1<=0;sy1<=0;sx2<=0;sy2<=0;
            draw_box1<=0;draw_bg1<=0;
            glyph0_1<=0;glyph1_1<=0;glyph2_1<=0;
        end else if(pipeline_enable)begin
            valid2<=valid1;
            valid1<=valid0;
            valid0<=s_axis_video_tvalid;

            if(s_axis_video_tvalid)begin
                data0<=s_axis_video_tdata;
                keep0<=s_axis_video_tkeep;
                last0<=s_axis_video_tlast;
                user0<=s_axis_video_tuser;
                px0<=s_axis_video_tuser?12'd0:pixel_x;
                py0<=s_axis_video_tuser?12'd0:pixel_y;
                sx0<=s_axis_video_tuser?cfg_x0_sync:cfg_x0_active;
                sy0<=s_axis_video_tuser?cfg_y0_sync:cfg_y0_active;
                sx1<=s_axis_video_tuser?cfg_x1_sync:cfg_x1_active;
                sy1<=s_axis_video_tuser?cfg_y1_sync:cfg_y1_active;
                sx2<=s_axis_video_tuser?cfg_x2_sync:cfg_x2_active;
                sy2<=s_axis_video_tuser?cfg_y2_sync:cfg_y2_active;
            end

            if(valid0)begin
                data1<=data0;
                keep1<=keep0;
                last1<=last0;
                user1<=user0;
                draw_box1<=calc_box;
                draw_bg1<=calc_bg;
                glyph0_1<=calc_glyph0;
                glyph1_1<=calc_glyph1;
                glyph2_1<=calc_glyph2;
            end

            if(valid1)begin
                data2<=(draw_text2||draw_box1)?BOX_COLOR:(draw_bg1?LABEL_BACKGROUND:data1);
                keep2<=keep1;
                last2<=last1;
                user2<=user1;
            end
        end
    end
endmodule
