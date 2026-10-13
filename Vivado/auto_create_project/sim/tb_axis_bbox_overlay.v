`timescale 1ns / 1ps

module tb_axis_bbox_overlay;
    reg         aclk = 1'b0;
    reg         aresetn = 1'b0;
    reg [31:0] cfg_x0=0, cfg_y0=0, cfg_x1=0, cfg_y1=0, cfg_x2=0, cfg_y2=0;
    reg  [23:0] s_tdata = 24'd0;
    reg  [2:0]  s_tkeep = 3'b111;
    reg         s_tlast = 1'b0;
    reg         s_tuser = 1'b0;
    reg         s_tvalid = 1'b0;
    wire        s_tready;
    wire [23:0] m_tdata;
    wire [2:0]  m_tkeep;
    wire        m_tlast;
    wire        m_tuser;
    wire        m_tvalid;
    reg         m_tready = 1'b1;

    integer errors = 0;
    integer x;
    integer y;
    reg exp_valid0=0, exp_valid1=0;
    reg exp_check0=0, exp_check1=0;
    reg [23:0] exp_data0=0, exp_data1=0;
    reg exp_last0=0, exp_last1=0, exp_user0=0, exp_user1=0;

    always #3.5 aclk = ~aclk;

    axis_bbox_overlay #(
        .BOX_COLOR(24'h00FF00),
        .BOX_THICKNESS(1)
    ) dut (
        .aclk(aclk),
        .aresetn(aresetn),
        .cfg_x0(cfg_x0), .cfg_y0(cfg_y0),
        .cfg_x1(cfg_x1), .cfg_y1(cfg_y1),
        .cfg_x2(cfg_x2), .cfg_y2(cfg_y2),
        .s_axis_video_tdata(s_tdata),
        .s_axis_video_tkeep(s_tkeep),
        .s_axis_video_tlast(s_tlast),
        .s_axis_video_tuser(s_tuser),
        .s_axis_video_tvalid(s_tvalid),
        .s_axis_video_tready(s_tready),
        .m_axis_video_tdata(m_tdata),
        .m_axis_video_tkeep(m_tkeep),
        .m_axis_video_tlast(m_tlast),
        .m_axis_video_tuser(m_tuser),
        .m_axis_video_tvalid(m_tvalid),
        .m_axis_video_tready(m_tready)
    );

    task advance_and_check;
        input reg [23:0] expected_pixel;
        input reg expected_last;
        input reg expected_user;
        input reg check_data;
        input reg new_valid;
        begin
            @(posedge aclk);
            #1;
            if(m_tvalid!==exp_valid1)begin
                $display("VALID_FAIL got=%b expected=%b",m_tvalid,exp_valid1);
                errors=errors+1;
            end
            if(exp_valid1&&(!m_tvalid||m_tkeep!==3'b111||m_tuser!==exp_user1||m_tlast!==exp_last1||
               (exp_check1&&m_tdata!==exp_data1)))begin
                $display("PIPE_FAIL data=%h expected=%h",m_tdata,exp_data1);
                errors=errors+1;
            end
            exp_valid1=exp_valid0;exp_data1=exp_data0;exp_last1=exp_last0;
            exp_user1=exp_user0;exp_check1=exp_check0;
            exp_valid0=new_valid;exp_data0=expected_pixel;exp_last0=expected_last;
            exp_user0=expected_user;exp_check0=check_data;
        end
    endtask

    task send_and_check;
        input integer px;
        input integer py;
        reg [23:0] source_pixel;
        reg [23:0] expected_pixel;
        reg expected_border;
        begin
            source_pixel = {py[7:0], px[7:0], 8'h55};
            expected_border = (((py == 1 || py == 3) && px >= 2 && px <= 5) ||
                              ((px == 2 || px == 5) && py >= 1 && py <= 3)) ||
                              (((py == 1 || py == 3) && px >= 7 && px <= 10) ||
                              ((px == 7 || px == 10) && py >= 1 && py <= 3));
            expected_pixel = expected_border ? 24'h00FF00 : source_pixel;

            @(negedge aclk);
            s_tdata = source_pixel;
            s_tuser = (px == 0 && py == 0);
            s_tlast = (px == 11);
            s_tvalid = 1'b1;
            if(!s_tready)begin $display("READY_FAIL");errors=errors+1;end
            advance_and_check(expected_pixel,s_tlast,s_tuser,1'b1,1'b1);
        end
    endtask

    task send_label_and_check;
        input integer px;
        input integer py;
        reg [23:0] source_pixel;
        begin
            source_pixel = {py[7:0], px[7:0], 8'h55};
            @(negedge aclk);
            s_tdata = source_pixel;
            s_tuser = 1'b0;
            s_tlast = (px == 11);
            s_tvalid = 1'b1;
            // y=4 is the black label background; y=5,x=2 is the first
            // green pixel of the scaled 'P' in "PEOPLE 1.2M".
            if(px==2&&py==4)
                advance_and_check(24'h000000,s_tlast,s_tuser,1'b1,1'b1);
            else if(px==2&&py==5)
                advance_and_check(24'h00FF00,s_tlast,s_tuser,1'b1,1'b1);
            else
                advance_and_check(source_pixel,s_tlast,s_tuser,1'b0,1'b1);
        end
    endtask

    initial begin
        repeat (4) @(posedge aclk);
        cfg_x0 = 32'h8005_0002;
        cfg_y0 = 32'h1003_2001; // BCD 12 dm => PEOPLE 1.2M label
        cfg_x1 = 32'h800A_0007;
        cfg_y1 = 32'h0003_C001; // 0x0c dm => PEOPLE 1.2M label
        aresetn = 1'b1;
        repeat (4) @(posedge aclk);

        // The labels for these near-top boxes begin at y=4.  This first pass
        // checks both independent box outlines without entering label pixels.
        for (y = 0; y < 4; y = y + 1)
            for (x = 0; x < 12; x = x + 1)
                send_and_check(x, y);

        for (y = 4; y < 6; y = y + 1)
            for (x = 0; x < 12; x = x + 1)
                send_label_and_check(x, y);

        @(negedge aclk);
        s_tvalid = 1'b0;
        advance_and_check(24'd0,1'b0,1'b0,1'b0,1'b0);
        @(negedge aclk);
        advance_and_check(24'd0,1'b0,1'b0,1'b0,1'b0);
        if (errors == 0) begin
            $display("BBOX_SIM_PASS");
            $finish;
        end
        $fatal(1, "BBOX_SIM_FAIL errors=%0d", errors);
    end
endmodule
