`timescale 1ns / 1ps

module tb_axis_bbox_overlay;
    reg         aclk = 1'b0;
    reg         aresetn = 1'b0;
    reg  [31:0] cfg_x = 32'd0;
    reg  [31:0] cfg_y = 32'd0;
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

    always #3.5 aclk = ~aclk;

    axis_bbox_overlay #(
        .BOX_COLOR(24'h00FF00),
        .BOX_THICKNESS(1)
    ) dut (
        .aclk(aclk),
        .aresetn(aresetn),
        .cfg_x(cfg_x),
        .cfg_y(cfg_y),
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

    task send_and_check;
        input integer px;
        input integer py;
        reg [23:0] source_pixel;
        reg [23:0] expected_pixel;
        reg expected_border;
        begin
            source_pixel = {py[7:0], px[7:0], 8'h55};
            expected_border = ((py == 1 || py == 3) && px >= 2 && px <= 5) ||
                              ((px == 2 || px == 5) && py >= 1 && py <= 3);
            expected_pixel = expected_border ? 24'h00FF00 : source_pixel;

            @(negedge aclk);
            s_tdata = source_pixel;
            s_tuser = (px == 0 && py == 0);
            s_tlast = (px == 7);
            s_tvalid = 1'b1;
            @(posedge aclk);
            if (!s_tready || !m_tvalid || m_tdata !== expected_pixel ||
                m_tkeep !== 3'b111 || m_tuser !== s_tuser || m_tlast !== s_tlast) begin
                $display("FAIL x=%0d y=%0d data=%h expected=%h", px, py, m_tdata, expected_pixel);
                errors = errors + 1;
            end
        end
    endtask

    initial begin
        repeat (4) @(posedge aclk);
        cfg_x = 32'h8005_0002;
        cfg_y = 32'h0003_0001;
        aresetn = 1'b1;
        repeat (4) @(posedge aclk);

        for (y = 0; y < 5; y = y + 1)
            for (x = 0; x < 8; x = x + 1)
                send_and_check(x, y);

        @(negedge aclk);
        s_tvalid = 1'b0;
        if (errors == 0) begin
            $display("BBOX_SIM_PASS");
            $finish;
        end
        $fatal(1, "BBOX_SIM_FAIL errors=%0d", errors);
    end
endmodule
